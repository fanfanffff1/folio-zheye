(function () {
  const stars = document.querySelector("[data-stars]");
  const form = document.getElementById("comment-form");
  const list = document.getElementById("comment-list");
  const status = document.getElementById("comment-status");
  if (!stars) return;
  const slug = stars.getAttribute("data-slug");
  const csrf = stars.getAttribute("data-csrf");
  let sort = "newest";
  let posting = false;

  async function jsonFetch(url, opts) {
    const res = await fetch(url, opts);
    const data = await res.json().catch(() => ({}));
    const msg = Array.isArray(data.detail)
      ? (data.detail[0] && (data.detail[0].msg || data.detail[0]))
      : data.detail;
    if (!res.ok) throw new Error(msg || data.message || "请求失败");
    return data;
  }

  function renderSummary(s) {
    const el = document.getElementById("rating-summary");
    el.textContent = s.count ? `平均 ${s.average} 分 · ${s.count} 人评分` : "暂无评分";
    stars.querySelectorAll("button").forEach((btn) => {
      const n = Number(btn.getAttribute("data-score"));
      btn.textContent = s.mine && s.mine >= n ? "★" : "☆";
    });
    const dist = document.getElementById("rating-dist");
    dist.innerHTML = [5, 4, 3, 2, 1]
      .map((n) => `<li>${n}星 ${s.distribution[n] || 0}</li>`)
      .join("");
  }

  stars.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-score]");
    if (!btn) return;
    try {
      const s = await jsonFetch(`/api/books/${slug}/ratings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ score: Number(btn.dataset.score), csrf }),
      });
      renderSummary(s);
    } catch (err) {
      status.textContent = err.message;
    }
  });

  function commentHtml(c, isReply) {
    const replies = (c.replies || [])
      .map((r) => commentHtml(r, true))
      .join("");
    return `<article class="comment ${isReply ? "replies" : ""}" data-id="${c.id}">
      <p><strong>${escapeHtml(c.nickname)}</strong> · <time>${c.createdAt.slice(0, 16).replace("T", " ")}</time></p>
      <p>${escapeHtml(c.content)}</p>
      <p>
        <button type="button" data-like="${c.id}" aria-pressed="${c.liked}">赞 ${c.likeCount}</button>
        ${isReply ? "" : `<button type="button" data-reply="${c.id}">回复</button>`}
        ${c.mine ? `<button type="button" data-edit="${c.id}">编辑</button><button type="button" data-del="${c.id}">删除</button>` : `<button type="button" data-report="${c.id}">举报</button>`}
      </p>
      ${replies}
    </article>`;
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  let offset = 0;
  let hasMore = false;

  async function loadComments(append) {
    if (!append) {
      offset = 0;
      list.innerHTML = "";
    }
    const data = await jsonFetch(`/api/books/${slug}/comments?sort=${sort}&offset=${offset}`);
    hasMore = data.hasMore;
    offset = (data.offset || 0) + (data.comments || []).length;
    const html = data.comments.length
      ? data.comments.map((c) => commentHtml(c, false)).join("")
      : append
        ? ""
        : "<p class='empty'>还没有评论。</p>";
    if (append) list.insertAdjacentHTML("beforeend", html);
    else list.innerHTML = html;
    let more = document.getElementById("load-more");
    if (!more) {
      more = document.createElement("button");
      more.id = "load-more";
      more.type = "button";
      more.textContent = "加载更多";
      list.after(more);
      more.addEventListener("click", () => loadComments(true).catch((e) => (status.textContent = e.message)));
    }
    more.hidden = !hasMore;
  }

  document.querySelectorAll("[data-sort]").forEach((btn) => {
    btn.addEventListener("click", () => {
      sort = btn.getAttribute("data-sort");
      loadComments().catch((e) => (status.textContent = e.message));
    });
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (posting) return;
    posting = true;
    status.textContent = "正在发布…";
    const fd = new FormData(form);
    try {
      await jsonFetch(`/api/books/${slug}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nickname: fd.get("nickname"),
          content: fd.get("content"),
          csrf,
          parent_id: fd.get("parent_id") ? Number(fd.get("parent_id")) : null,
        }),
      });
      form.reset();
      const hidden = form.querySelector("[name=parent_id]");
      if (hidden) hidden.remove();
      status.textContent = "已发布。";
      await loadComments();
    } catch (err) {
      status.textContent = err.message;
    } finally {
      posting = false;
    }
  });

  list.addEventListener("click", async (e) => {
    const like = e.target.closest("[data-like]");
    const reply = e.target.closest("[data-reply]");
    const del = e.target.closest("[data-del]");
    const edit = e.target.closest("[data-edit]");
    const report = e.target.closest("[data-report]");
    try {
      if (like) {
        const data = await jsonFetch(`/api/comments/${like.getAttribute("data-like")}/like`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ csrf }),
        });
        like.textContent = `赞 ${data.likeCount}`;
        like.setAttribute("aria-pressed", data.liked);
      }
      if (reply) {
        let hidden = form.querySelector("[name=parent_id]");
        if (!hidden) {
          hidden = document.createElement("input");
          hidden.type = "hidden";
          hidden.name = "parent_id";
          form.appendChild(hidden);
        }
        hidden.value = reply.getAttribute("data-reply");
        status.textContent = "正在回复该评论。";
        form.querySelector("[name=content]").focus();
      }
      if (del) {
        await jsonFetch(`/api/comments/${del.getAttribute("data-del")}/delete`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ csrf }),
        });
        await loadComments();
      }
      if (edit) {
        const next = prompt("修改评论");
        if (next) {
          await jsonFetch(`/api/comments/${edit.getAttribute("data-edit")}/edit`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ csrf, content: next }),
          });
          await loadComments();
        }
      }
      if (report) {
        await jsonFetch(`/api/comments/${report.getAttribute("data-report")}/report`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ csrf, reason: "读者举报" }),
        });
        status.textContent = "已提交举报，进入审核。";
      }
    } catch (err) {
      status.textContent = err.message;
    }
  });

  loadComments().catch((e) => (status.textContent = e.message));
})();
