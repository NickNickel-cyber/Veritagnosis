(function () {
  'use strict';
  if (window.__vgLab) return;
  window.__vgLab = true;

  var editor = function () { return document.getElementById('vg-editor'); };

  /* The same rule the server splits on, so the two numbers never disagree. */
  var WORD_RE = /[A-Za-z][A-Za-z'’\-]*/g;

  function count(text) {
    var m = (text || '').match(WORD_RE);
    return m ? m.length : 0;
  }

  function paintCount() {
    var box = editor();
    var live = document.getElementById('vg-live');
    if (!box || !live) return;

    var n = count(box.value);
    var floor = parseInt(live.getAttribute('data-floor'), 10) || 60;
    var target = parseInt(live.getAttribute('data-target'), 10) || 650;

    var msg;
    if (n === 0) {
      msg = 'No words yet';
    } else if (n < floor) {
      var left = floor - n;
      msg = n + (n === 1 ? ' word' : ' words') + ' · ' + left +
            ' more before scoring starts';
    } else if (n <= target) {
      msg = n + ' words · ' + (target - n) + ' left';
    } else {
      msg = n + ' words · ' + (n - target) + ' over the limit';
    }

    if (live.textContent !== msg) live.textContent = msg;
    live.setAttribute('data-state',
      n === 0 ? 'empty' : n < floor ? 'early' : n > target ? 'over' : 'ok');

    /* The header number is rendered by the server too. Both write the same
       value from the same rule, so they converge rather than fight. */
    var head = document.querySelector('.lab-words');
    if (head) {
      var t = n + ' words';
      if (head.textContent !== t) head.textContent = t;
    }
  }

  function drawer() { return document.getElementById('vg-coach'); }

  function drawerOpen() {
    var d = drawer();
    return !!d && d.getAttribute('data-open') === 'true' &&
           window.innerWidth < 1080;
  }

  function closeDrawer() {
    var b = document.getElementById('vg-coach-toggle');
    if (b) b.click();
  }

  function promptModalOpen() {
    return !!document.getElementById('vg-prompt-modal');
  }

  function closePromptModal() {
    var b = document.getElementById('vg-prompt-close');
    if (b) b.click();
  }

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    if (promptModalOpen()) { closePromptModal(); return; }
    if (drawerOpen()) closeDrawer();
  }, false);

  document.addEventListener('pointerdown', function (e) {
    if (!drawerOpen()) return;
    var d = drawer();
    var toggle = document.getElementById('vg-coach-toggle');
    if (d && d.contains(e.target)) return;
    if (toggle && toggle.contains(e.target)) return;
    closeDrawer();
  }, false);

  /* Reflex replaces nodes on re-render, so a listener bound to the textarea
     would be thrown away with it. Listening on the document survives that. */
  document.addEventListener('input', function (e) {
    if (e.target && e.target.id === 'vg-editor') paintCount();
  }, false);

  /* And a cheap poll catches the cases no input event covers: the first
     paint, a draft loaded from the server, a fix applied, an undo. */
  setInterval(paintCount, 400);
  paintCount();
})();
