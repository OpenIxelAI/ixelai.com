// The docs pages' script: tabs for each system, and the menu on a phone. It stores nothing and sends
// nothing: your system is read from the browser each time, never saved.

(function () {
  // The menu starts open (so it works without this script); on a narrow screen it starts closed
  var menu = document.querySelector(".docs-nav details");
  var narrow = window.matchMedia && window.matchMedia("(max-width: 760px)");
  if (menu && narrow) {
    var fit = function () { menu.open = !narrow.matches; };
    fit();
    if (narrow.addEventListener) narrow.addEventListener("change", fit);
  }
})();

// Tabs: .tabs holds .tab-panel elements, each with data-tab and a .tab-title heading. The script adds the
// buttons, picks the tab for this computer's system, and keeps every tab group on the page on the same one.
(function () {
  var groups = document.querySelectorAll(".tabs");
  if (!groups.length) return;
  var platform = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "";
  var agent = navigator.userAgent || "";
  var mine = /Win/i.test(platform) ? "windows" : /Mac|iPhone|iPad/i.test(platform + agent) ? "mac"
    : /Linux|X11|CrOS/i.test(platform + agent) ? "linux" : "";

  for (var i = 0; i < groups.length; i++) build(groups[i]);
  var first = groups[0].querySelector('.tab-panel[data-tab="' + mine + '"]');
  select(first ? mine : groups[0].querySelector(".tab-panel").getAttribute("data-tab"));

  function build(group) {
    var panels = group.querySelectorAll(":scope > .tab-panel");
    var list = document.createElement("div");
    list.className = "tab-list";
    list.setAttribute("role", "tablist");
    for (var j = 0; j < panels.length; j++) {
      var panel = panels[j];
      var key = panel.getAttribute("data-tab");
      var title = panel.querySelector(".tab-title");
      var button = document.createElement("button");
      button.type = "button";
      button.setAttribute("role", "tab");
      button.setAttribute("data-tab", key);
      button.textContent = title ? title.textContent : key;
      if (!panel.id) panel.id = "tab-" + key + "-" + Math.random().toString(36).slice(2, 8);
      button.setAttribute("aria-controls", panel.id);
      panel.setAttribute("role", "tabpanel");
      button.addEventListener("click", function () { select(this.getAttribute("data-tab")); });
      button.addEventListener("keydown", arrows);
      list.appendChild(button);
    }
    group.insertBefore(list, group.firstChild);
    group.className += " ready";
  }

  function arrows(e) {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    var buttons = Array.prototype.slice.call(this.parentNode.children);
    var at = buttons.indexOf(this) + (e.key === "ArrowRight" ? 1 : -1);
    var next = buttons[(at + buttons.length) % buttons.length];
    select(next.getAttribute("data-tab"));
    next.focus();
  }

  function select(key) {
    for (var i = 0; i < groups.length; i++) {
      var group = groups[i];
      if (!group.querySelector(':scope > .tab-panel[data-tab="' + key + '"]')) continue;
      var buttons = group.querySelectorAll(".tab-list button");
      for (var j = 0; j < buttons.length; j++) {
        var on = buttons[j].getAttribute("data-tab") === key;
        buttons[j].setAttribute("aria-selected", on ? "true" : "false");
        buttons[j].tabIndex = on ? 0 : -1;
      }
      var panels = group.querySelectorAll(":scope > .tab-panel");
      for (var k = 0; k < panels.length; k++) panels[k].hidden = panels[k].getAttribute("data-tab") !== key;
    }
  }
})();
