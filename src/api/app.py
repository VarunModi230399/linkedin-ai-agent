# TODO: implement src/api/app.py
# src/api/app.py
#
# FastAPI application for the LinkedIn AI Agent.
# Serves the approval UI and handles approval decisions.
#
# Routes:
#   GET  /              → dashboard (list pending posts)
#   GET  /pending       → JSON list of pending posts
#   GET  /posts/{id}    → view single post detail
#   POST /posts/{id}/approve → approve post
#   POST /posts/{id}/reject  → reject with feedback
#   POST /posts/{id}/edit    → approve with edits
#   GET  /health        → health check

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from src.agent.core.settings import DATABASE_URL
import uuid
import json
from datetime import datetime

# ── App instance ──────────────────────────────────
app = FastAPI(
    title="LinkedIn AI Agent — Approval UI",
    description="Review and approve AI-generated LinkedIn posts",
    version="1.0.0",
)

# ── In-memory post store (Phase 6 testing) ────────
# Switches to PostgreSQL in Phase 8
# Key: post_id, Value: post dict
POST_STORE: dict[str, dict] = {}


# ── Request/Response models ───────────────────────
class ApproveRequest(BaseModel):
    notes: str = ""


class RejectRequest(BaseModel):
    feedback: str
    notes: str = ""


class EditRequest(BaseModel):
    edited_content: str
    notes: str = ""


# ── Helper functions ──────────────────────────────
def create_post_record(
    draft: str,
    pillar: str,
    selected_idea: str,
    critique: dict,
    critique_score: float,
) -> str:
    """
    Creates a post record in the store.
    Returns the post_id.
    """
    post_id = str(uuid.uuid4())
    POST_STORE[post_id] = {
        "id": post_id,
        "content": draft,
        "pillar": pillar,
        "idea": selected_idea,
        "critique": critique,
        "critique_score": critique_score,
        "status": "pending_approval",
        "created_at": datetime.utcnow().isoformat(),
        "decided_at": None,
        "reviewer_notes": "",
        "edited_content": None,
        "diff": None,
    }
    return post_id


# ── Routes ────────────────────────────────────────


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "posts_pending": len(
            [p for p in POST_STORE.values() if p["status"] == "pending_approval"]
        ),
    }


@app.post("/posts")
def submit_post(post_data: dict):
    """
    Called by the agent to submit a post for review.
    Returns the post_id for polling.
    """
    post_id = create_post_record(
        draft=post_data.get("draft", ""),
        pillar=post_data.get("pillar", ""),
        selected_idea=post_data.get("selected_idea", ""),
        critique=post_data.get("critique", {}),
        critique_score=post_data.get("critique_score", 0.0),
    )
    print(f"📬 New post submitted for review: {post_id[:8]}...")
    print(f"   Idea: {post_data.get('selected_idea', '')[:55]}")
    return {"post_id": post_id, "status": "pending_approval"}


@app.get("/posts/{post_id}/status")
def get_post_status(post_id: str):
    """
    Called by the agent to poll for a decision.
    Returns current status of the post.
    """
    post = POST_STORE.get(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    return {
        "post_id": post_id,
        "status": post["status"],
        "content": post.get("content", ""),
        "reviewer_notes": post.get("reviewer_notes", ""),
    }


@app.get("/pending")
def get_pending_posts():
    """Returns all posts awaiting approval."""
    pending = [p for p in POST_STORE.values() if p["status"] == "pending_approval"]
    return {"posts": pending, "count": len(pending)}


@app.get("/posts/{post_id}")
def get_post(post_id: str):
    """Returns a single post by ID."""
    post = POST_STORE.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@app.post("/posts/{post_id}/approve")
def approve_post(post_id: str, req: ApproveRequest):
    """Approves a post as-is."""
    post = POST_STORE.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["status"] != "pending_approval":
        raise HTTPException(status_code=400, detail="Post is not pending approval")

    POST_STORE[post_id].update(
        {
            "status": "approved",
            "decided_at": datetime.utcnow().isoformat(),
            "reviewer_notes": req.notes,
        }
    )

    print(f"✅ Post {post_id[:8]}... approved")
    return {"status": "approved", "post_id": post_id}


@app.post("/posts/{post_id}/reject")
def reject_post(post_id: str, req: RejectRequest):
    """Rejects a post and sends it back for rewriting."""
    post = POST_STORE.get(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    if post["status"] != "pending_approval":
        raise HTTPException(400, "Post is not pending approval")

    POST_STORE[post_id].update(
        {
            "status": "rejected",
            "decided_at": datetime.utcnow().isoformat(),
            "reviewer_notes": req.feedback,
        }
    )

    print(f"❌ Post {post_id[:8]}... rejected — {req.feedback}")
    return {"status": "rejected", "post_id": post_id, "feedback": req.feedback}


@app.post("/posts/{post_id}/edit")
def approve_with_edit(post_id: str, req: EditRequest):
    """
    Approves a post with human edits.
    Stores the diff as a training signal.
    """
    post = POST_STORE.get(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    if post["status"] != "pending_approval":
        raise HTTPException(400, "Post is not pending approval")

    # Compute simple diff — count changed lines
    original_lines = post["content"].splitlines()
    edited_lines = req.edited_content.splitlines()

    added = [l for l in edited_lines if l not in original_lines]
    removed = [l for l in original_lines if l not in edited_lines]

    diff_summary = {
        "lines_added": len(added),
        "lines_removed": len(removed),
        "original_length": len(post["content"]),
        "edited_length": len(req.edited_content),
    }

    POST_STORE[post_id].update(
        {
            "status": "approved_with_edit",
            "content": req.edited_content,
            "edited_content": req.edited_content,
            "decided_at": datetime.utcnow().isoformat(),
            "reviewer_notes": req.notes,
            "diff": diff_summary,
        }
    )

    print(f"✏️  Post {post_id[:8]}... approved with edits")
    print(f"   Lines added: {len(added)}, removed: {len(removed)}")
    return {
        "status": "approved_with_edit",
        "post_id": post_id,
        "diff": diff_summary,
    }


# ── Dashboard UI ──────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def dashboard():
    """
    Simple HTML dashboard for reviewing posts.
    No React, no build step — just HTML + vanilla JS.
    """
    pending = [p for p in POST_STORE.values() if p["status"] == "pending_approval"]
    approved = [
        p
        for p in POST_STORE.values()
        if p["status"] in ("approved", "approved_with_edit")
    ]
    rejected = [p for p in POST_STORE.values() if p["status"] == "rejected"]

    posts_json = json.dumps(list(POST_STORE.values()), indent=2)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>LinkedIn AI Agent — Approval UI</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{font-family:'Inter',system-ui,sans-serif;background:#f5f4f0;color:#1a1a1a;}}
  header{{background:#fff;border-bottom:1px solid #ddd;padding:16px 24px;
    display:flex;align-items:center;justify-content:space-between;}}
  header h1{{font-size:16px;font-weight:700;}}
  .stats{{display:flex;gap:12px;}}
  .stat{{background:#f0efe9;border:1px solid #ddd;border-radius:8px;
    padding:8px 14px;font-size:13px;font-weight:600;}}
  .stat.pending{{background:#fff7ed;border-color:#fed7aa;color:#c2410c;}}
  .stat.approved{{background:#f0fdf4;border-color:#bbf7d0;color:#15803d;}}
  .stat.rejected{{background:#fef2f2;border-color:#fecaca;color:#dc2626;}}
  main{{max-width:900px;margin:24px auto;padding:0 20px;}}
  .section-title{{font-size:13px;font-weight:700;color:#888;
    text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px;}}
  .post-card{{background:#fff;border:1px solid #ddd;border-radius:12px;
    padding:20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.06);}}
  .post-meta{{display:flex;align-items:center;gap:8px;margin-bottom:12px;}}
  .pillar-badge{{background:#eef2ff;border:1px solid #c7d2fe;color:#4338ca;
    font-size:11px;font-weight:700;padding:3px 8px;border-radius:20px;}}
  .score-badge{{background:#f0fdf4;border:1px solid #bbf7d0;color:#15803d;
    font-size:11px;font-weight:700;padding:3px 8px;border-radius:20px;}}
  .idea{{font-size:13px;color:#555;margin-bottom:12px;font-style:italic;}}
  .post-content{{background:#f8f8f5;border:1px solid #e8e7e0;border-radius:8px;
    padding:14px;font-size:13px;line-height:1.7;white-space:pre-wrap;
    margin-bottom:14px;max-height:200px;overflow-y:auto;}}
  .scores-row{{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap;}}
  .score-item{{font-size:11px;background:#f0efe9;border:1px solid #ddd;
    border-radius:4px;padding:3px 8px;}}
  .actions{{display:flex;gap:8px;}}
  .btn{{padding:8px 16px;border-radius:6px;font-size:13px;font-weight:600;
    cursor:pointer;border:none;font-family:inherit;transition:all .15s;}}
  .btn-approve{{background:#16a34a;color:#fff;}}
  .btn-approve:hover{{background:#15803d;}}
  .btn-reject{{background:#dc2626;color:#fff;}}
  .btn-reject:hover{{background:#b91c1c;}}
  .btn-edit{{background:#4f46e5;color:#fff;}}
  .btn-edit:hover{{background:#4338ca;}}
  .modal-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.4);
    z-index:100;align-items:center;justify-content:center;}}
  .modal-overlay.open{{display:flex;}}
  .modal{{background:#fff;border-radius:14px;padding:24px;width:90%;
    max-width:560px;box-shadow:0 8px 32px rgba(0,0,0,.12);}}
  .modal h3{{font-size:15px;font-weight:700;margin-bottom:12px;}}
  textarea.modal-input{{width:100%;border:1px solid #ddd;border-radius:8px;
    padding:10px;font-size:13px;font-family:inherit;resize:vertical;outline:none;}}
  textarea.modal-input:focus{{border-color:#4f46e5;}}
  .modal-actions{{display:flex;gap:8px;justify-content:flex-end;margin-top:14px;}}
  .btn-cancel{{background:#f0efe9;color:#555;}}
  .empty-state{{text-align:center;padding:48px;color:#888;font-size:14px;}}
</style>
</head>
<body>
<header>
  <h1>⚡ LinkedIn AI Agent — Approval UI</h1>
  <div class="stats">
    <div class="stat pending">⏳ {len(pending)} Pending</div>
    <div class="stat approved">✅ {len(approved)} Approved</div>
    <div class="stat rejected">❌ {len(rejected)} Rejected</div>
  </div>
</header>

<main>
  <div id="pending-section">
    <div class="section-title">Pending Approval</div>
    <div id="pending-posts">
      {
        "".join([render_post_card(p) for p in pending])
        if pending
        else '<div class="empty-state">No posts pending approval.<br>Run the agent to generate a new post.</div>'
    }
    </div>
  </div>
</main>

<!-- Reject Modal -->
<div class="modal-overlay" id="reject-modal">
  <div class="modal">
    <h3>Reject Post</h3>
    <textarea class="modal-input" id="reject-feedback"
      placeholder="What should be changed? (required)"
      rows="4"></textarea>
    <div class="modal-actions">
      <button class="btn btn-cancel" onclick="closeModal('reject-modal')">Cancel</button>
      <button class="btn btn-reject" onclick="confirmReject()">Reject</button>
    </div>
  </div>
</div>

<!-- Edit Modal -->
<div class="modal-overlay" id="edit-modal">
  <div class="modal">
    <h3>Edit and Approve</h3>
    <textarea class="modal-input" id="edit-content"
      rows="12"></textarea>
    <div class="modal-actions">
      <button class="btn btn-cancel" onclick="closeModal('edit-modal')">Cancel</button>
      <button class="btn btn-edit" onclick="confirmEdit()">Approve with Edits</button>
    </div>
  </div>
</div>

<script>
let currentPostId = null;
const posts = {posts_json};

function openRejectModal(postId) {{
  currentPostId = postId;
  document.getElementById('reject-feedback').value = '';
  document.getElementById('reject-modal').classList.add('open');
}}

function openEditModal(postId) {{
  currentPostId = postId;
  const post = posts.find(p => p.id === postId);
  document.getElementById('edit-content').value = post ? post.content : '';
  document.getElementById('edit-modal').classList.add('open');
}}

function closeModal(id) {{
  document.getElementById(id).classList.remove('open');
  currentPostId = null;
}}

async function approvePost(postId) {{
  const res = await fetch(`/posts/${{postId}}/approve`, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{notes: ''}})
  }});
  if (res.ok) {{
    alert('✅ Post approved!');
    location.reload();
  }} else {{
    alert('Error approving post');
  }}
}}

async function confirmReject() {{
  const feedback = document.getElementById('reject-feedback').value.trim();
  if (!feedback) {{ alert('Please add feedback'); return; }}
  const res = await fetch(`/posts/${{currentPostId}}/reject`, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{feedback}})
  }});
  if (res.ok) {{
    closeModal('reject-modal');
    alert('❌ Post rejected');
    location.reload();
  }}
}}

async function confirmEdit() {{
  const edited = document.getElementById('edit-content').value.trim();
  if (!edited) {{ alert('Please add your edited version'); return; }}
  const res = await fetch(`/posts/${{currentPostId}}/edit`, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{edited_content: edited, notes: 'Human edited'}})
  }});
  if (res.ok) {{
    closeModal('edit-modal');
    alert('✏️ Post approved with edits!');
    location.reload();
  }}
}}
</script>
</body>
</html>"""
    return html


def render_post_card(post: dict) -> str:
    """Renders a single post card as HTML string."""
    critique = post.get("critique", {})
    scores_html = "".join(
        [
            f'<span class="score-item">{k.title()}: {v}/10</span>'
            for k, v in critique.items()
            if k != "feedback" and isinstance(v, (int, float))
        ]
    )

    return f"""
<div class="post-card">
  <div class="post-meta">
    <span class="pillar-badge">{post.get("pillar", "unknown")}</span>
    <span class="score-badge">⭐ {post.get("critique_score", 0)}/10</span>
  </div>
  <div class="idea">💡 {post.get("idea", "")}</div>
  <div class="post-content">{post.get("content", "")}</div>
  <div class="scores-row">{scores_html}</div>
  <div class="actions">
    <button class="btn btn-approve" onclick="approvePost('{post["id"]}')">
      ✅ Approve
    </button>
    <button class="btn btn-edit" onclick="openEditModal('{post["id"]}')">
      ✏️ Edit
    </button>
    <button class="btn btn-reject" onclick="openRejectModal('{post["id"]}')">
      ❌ Reject
    </button>
  </div>
</div>"""
