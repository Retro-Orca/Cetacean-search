// 鯨類まとめサイト - 補助JS

(function () {
  function setupBbsCounter() {
    var input = document.getElementById('bbs-message');
    var counter = document.getElementById('bbs-counter');
    if (!input || !counter) return;

    var max = parseInt(input.getAttribute('maxlength') || '0', 10);
    function update() {
      var len = (input.value || '').length;
      if (max > 0) {
        counter.textContent = '（' + len + '/' + max + '）';
      } else {
        counter.textContent = '（' + len + '）';
      }
    }
    input.addEventListener('input', update);
    update();
  }

  document.addEventListener('DOMContentLoaded', function () {
    setupBbsCounter();
  });
})();
