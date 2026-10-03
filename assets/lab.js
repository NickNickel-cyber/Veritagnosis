/* The Essay Lab's own behaviour.
 *
 * Kept apart from essay.js on purpose: that file owns read-aloud, focus mode
 * and the sprint clock, and none of this has anything to do with those.
 *
 * Two jobs, both of which exist because a round trip to the server is the
 * wrong tool for them:
 *
 *   1. The live count. The server re-reads the draft once it has moved by a
 *      sentence's worth of typing, which is right for the analysis and far too
 *      slow for a number that sits next to your cursor. A word counter that
 *      lags forty characters behind the words feels broken. This one does not
 *      lag, and it is also the honest place to say how much further there is
 *      to go before the draft can be scored at all.
 *
 *   2. The drawer. Below 1080px the coach panel slides over the writing, and
 *      anything that slides over the writing has to close the way every other
 *      panel on the web closes: Escape, or a click outside it.
 */
(function () {
  'use strict';
  if (window.__vgLab) return;
  window.__vgLab = true;

  var editor = function () { return document.getElementById('vg-editor'); };

  /* ---------------------------------------------------------------- count */

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
      /* Below the floor there is no score, and saying so plainly is the
         whole point: a number invented from forty words is what made the
         old screen feel like it was guessing. */
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

  /* ---------------------------------------------------------------- drawer */

  function drawer() { return document.getElementById('vg-coach'); }

  function drawerOpen() {
    var d = drawer();
    return !!d && d.getAttribute('data-open') === 'true' &&
           window.innerWidth < 1080;
  }

  /* The open state lives on the server, so closing means pressing the same
     button the student would have pressed. Setting the attribute here would
     desynchronise the two and the next render would snap it back open. */
  function closeDrawer() {
    var b = document.getElementById('vg-coach-toggle');
    if (b) b.click();
  }

  /* ---------------------------------------------------------------- modal */

  /* The prompt chooser. Escape has to close it, and it has to take priority
     over the drawer: when both are open the modal is the thing on top, and
     dismissing the thing underneath it first would be wrong. */
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

  /* ---------------------------------------------------------------- wiring */

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
