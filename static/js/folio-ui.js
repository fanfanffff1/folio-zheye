(function () {
  const header = document.querySelector("[data-header]");
  if (header) {
    const onScroll = function () {
      header.classList.toggle("is-scrolled", window.scrollY > 10);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  const rail = document.querySelector("[data-lang-scroller]");
  const next = document.querySelector("[data-lang-next]");
  if (rail && next) {
    const update = function () {
      const overflow = rail.scrollWidth - rail.clientWidth > 8;
      next.hidden = !overflow;
      next.disabled = rail.scrollLeft + rail.clientWidth >= rail.scrollWidth - 8;
    };
    next.addEventListener("click", function () {
      rail.scrollBy({ left: Math.min(rail.clientWidth * 0.72, 320), behavior: "smooth" });
    });
    rail.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    update();
  }

  const btn = document.querySelector("[data-menu]");
  const nav = document.querySelector("[data-nav]");
  if (!btn || !nav) return;

  const closeBtn = document.querySelector("[data-menu-close]");
  const close = function () {
    const wasOpen = nav.classList.contains("open");
    nav.classList.remove("open");
    btn.setAttribute("aria-expanded", "false");
    document.body.classList.remove("nav-open");
    if (wasOpen && window.matchMedia("(max-width: 767px)").matches) btn.focus();
  };
  const open = function () {
    nav.classList.add("open");
    btn.setAttribute("aria-expanded", "true");
    document.body.classList.add("nav-open");
    if (closeBtn) closeBtn.focus();
    else {
      const first = nav.querySelector("a");
      if (first) first.focus();
    }
  };
  btn.addEventListener("click", function () {
    if (nav.classList.contains("open")) close();
    else open();
  });
  if (closeBtn) closeBtn.addEventListener("click", close);
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && nav.classList.contains("open")) close();
  });
  nav.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", function () {
      if (nav.classList.contains("open")) close();
    });
  });
})();
