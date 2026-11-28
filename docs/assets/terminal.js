/* 文档站主题切换：跟随系统，手动选择写入 localStorage。 */
(function () {
  var KEY = 'vs-docs-theme';
  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) { /* file:// 下可能不可用 */ }
  var prefersLight = false;
  try { prefersLight = window.matchMedia('(prefers-color-scheme: light)').matches; } catch (e) {}
  var theme = saved === 'light' || saved === 'dark' ? saved : (prefersLight ? 'light' : 'dark');
  document.documentElement.setAttribute('data-theme', theme);

  function sync() {
    var btn = document.querySelector('[data-theme-toggle]');
    if (btn) {
      btn.textContent = document.documentElement.getAttribute('data-theme') === 'dark' ? '☾' : '☀';
      btn.setAttribute('aria-label', document.documentElement.getAttribute('data-theme') === 'dark' ? '切换到浅色' : '切换到深色');
    }
  }

  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!(t instanceof Element)) return;
    if (!t.closest('[data-theme-toggle]')) return;
    var next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem(KEY, next); } catch (err) {}
    sync();
  });

  document.addEventListener('DOMContentLoaded', function () {
    sync();
    // 目录高亮：当前可视小节
    var links = Array.prototype.slice.call(document.querySelectorAll('.toc a[href^="#"]'));
    if (!links.length) return;
    var targets = links.map(function (a) {
      return document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1)));
    });
    function onScroll() {
      var y = window.scrollY + 120;
      var idx = 0;
      for (var i = 0; i < targets.length; i++) {
        if (targets[i] && targets[i].offsetTop <= y) idx = i;
      }
      links.forEach(function (a, i) { a.classList.toggle('on', i === idx); });
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  });
})();
