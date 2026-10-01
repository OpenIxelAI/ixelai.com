// IxelAI site script, shared by every page.

(function () {
  var year = document.getElementById("year");
  if (year) year.textContent = new Date().getFullYear();
})();

// A quiet starfield behind the page, in the colors of the Ixel mark.
(function () {
  var canvas = document.getElementById("sky");
  var ctx = canvas.getContext && canvas.getContext("2d");
  if (!ctx) return;
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var tints = ["200,216,232", "232,240,247", "126,184,212", "155,127,199", "212,175,55"];
  var stars = [], w = 0, h = 0, frame = 0;

  function seed() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = canvas.clientWidth;
    h = canvas.clientHeight;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    var count = Math.round((w * h) / 7000);
    stars = [];
    for (var i = 0; i < count; i++) {
      var big = Math.random() < 0.06;
      stars.push({
        x: Math.random() * w,
        y: Math.random() * h,
        r: big ? 1 + Math.random() * 0.8 : 0.3 + Math.random() * 0.7,
        a: 0.15 + Math.random() * 0.5,
        phase: Math.random() * Math.PI * 2,
        speed: 0.2 + Math.random() * 0.8,
        tint: Math.random() < 0.82 ? tints[0] : tints[1 + Math.floor(Math.random() * 4)]
      });
    }
  }

  function draw(t) {
    ctx.clearRect(0, 0, w, h);
    for (var i = 0; i < stars.length; i++) {
      var s = stars[i];
      var shimmer = still ? 1 : 0.6 + 0.4 * Math.sin(s.phase + t * 0.0008 * s.speed);
      ctx.fillStyle = "rgba(" + s.tint + "," + (s.a * shimmer).toFixed(3) + ")";
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function loop(t) {
    draw(t);
    frame = requestAnimationFrame(loop);
  }

  function start() {
    cancelAnimationFrame(frame);
    seed();
    if (still) draw(0); else frame = requestAnimationFrame(loop);
  }

  var resizeTimer;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(start, 150);
  });
  start();
})();

// Copy buttons on the install commands.
(function () {
  var blocks = document.querySelectorAll("pre.code");
  for (var i = 0; i < blocks.length; i++) addCopy(blocks[i]);

  function addCopy(pre) {
    var code = pre.querySelector("code");
    var button = document.createElement("button");
    button.type = "button";
    button.className = "copy";
    button.textContent = "Copy";
    button.addEventListener("click", function () {
      var text = code.innerText.replace(/\s+$/, "");
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(copied, selectIt);
      } else {
        selectIt();
      }
    });
    pre.appendChild(button);

    function copied() {
      button.textContent = "Copied";
      setTimeout(function () { button.textContent = "Copy"; }, 1600);
    }
    function selectIt() {
      var range = document.createRange();
      range.selectNodeContents(code);
      var selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      button.textContent = "Press Ctrl+C";
    }
  }
})();

// Demo videos: a page shows its recording once the file is in videos/, and the example screen until then.
(function () {
  var demos = document.querySelectorAll("[data-demo]");
  if (!window.fetch) return;
  for (var i = 0; i < demos.length; i++) show(demos[i]);

  function show(figure) {
    var video = figure.querySelector("video");
    var src = video && video.getAttribute("data-src");
    if (!src) return;
    fetch(src, { method: "HEAD" }).then(function (response) {
      if (!response.ok) return;
      video.src = src;
      video.hidden = false;
      var fallback = figure.querySelector(".demo-fallback");
      if (fallback) fallback.hidden = true;
    }).catch(function () {});
  }
})();
