/*
 * PNG download for dashboard cards and the whole page.
 *
 * Buttons: <button class="dl-btn" data-target="<element id>" data-name="<file stem>">
 *
 * How it works: html2canvas renders the card's HTML (titles, KPIs, table, logos) with each
 * Plotly graph hidden, then every graph is rasterised with Plotly.toImage (which also handles
 * the WebGL map) and drawn onto the final canvas at its measured position.
 */
(function () {
  var SCALE = 2;
  var CREDIT = "A Between the Pipes project · betweenthepipes.substack.com · Data: Doug Kroll (Jet Tip)";

  function fileStamp() {
    var d = new Date();
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }

  function slug(s) {
    return (s || "nfl-charter-flights").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }

  function bg(el) {
    var node = el;
    while (node && node !== document.documentElement) {
      var c = getComputedStyle(node).backgroundColor;
      if (c && c !== "rgba(0, 0, 0, 0)" && c !== "transparent") return c;
      node = node.parentElement;
    }
    return getComputedStyle(document.body).backgroundColor;
  }

  function loadImage(src) {
    return new Promise(function (resolve, reject) {
      var img = new Image();
      img.onload = function () { resolve(img); };
      img.onerror = reject;
      img.src = src;
    });
  }

  // Position of `el` relative to `root` (both in the same document).
  function offsetWithin(el, root) {
    var r = el.getBoundingClientRect();
    var rr = root.getBoundingClientRect();
    return { x: r.left - rr.left, y: r.top - rr.top };
  }

  async function render(target) {
    var plots = Array.prototype.slice.call(target.querySelectorAll(".js-plotly-plot"));
    var images = await Promise.all(plots.map(function (gd) {
      return window.Plotly.toImage(gd, {
        format: "png", width: gd.offsetWidth, height: gd.offsetHeight, scale: SCALE,
      }).then(loadImage);
    }));
    // Filled in from the html2canvas clone, whose layout differs from the live page
    // (ignored elements removed, scroll boxes expanded).
    var placements = [];

    var mutedColor = (getComputedStyle(document.documentElement).getPropertyValue("--muted") || "#8a8984").trim();

    var canvas = await window.html2canvas(target, {
      scale: SCALE,
      useCORS: true,
      logging: false,
      backgroundColor: bg(target),
      onclone: function (doc) {
        var clone = doc.getElementById(target.id);
        // Cards in a grid row stretch to the tallest sibling; export at natural height.
        clone.style.alignSelf = "start";
        clone.style.height = "auto";
        // Show the full content of scrollable areas (e.g. the 32-team bar chart).
        clone.querySelectorAll(".scroll").forEach(function (el) {
          el.style.maxHeight = "none";
          el.style.overflow = "visible";
        });
        var credit = doc.createElement("div");
        credit.textContent = CREDIT;
        credit.style.cssText = "font-size:12px;margin-top:10px;text-align:right;color:" + mutedColor + ";";
        clone.appendChild(credit);
        // Measure graph positions in the final clone layout, then hide them so
        // html2canvas leaves their space empty for the Plotly images.
        clone.querySelectorAll(".js-plotly-plot").forEach(function (el, i) {
          var pos = offsetWithin(el, clone);
          placements[i] = { x: pos.x, y: pos.y, w: plots[i].offsetWidth, h: plots[i].offsetHeight };
          el.style.visibility = "hidden";
        });
      },
    });

    var ctx = canvas.getContext("2d");
    // html2canvas leaves its scale/translate transform on the context; draw in raw pixels.
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    images.forEach(function (img, i) {
      var p = placements[i];
      ctx.drawImage(img, p.x * SCALE, p.y * SCALE, p.w * SCALE, p.h * SCALE);
    });
    return canvas;
  }

  function flash(btn, text) {
    btn.textContent = text;
    setTimeout(function () { btn.textContent = btn.dataset.label; btn.disabled = false; }, 1600);
  }

  async function handle(btn) {
    var target = document.getElementById(btn.dataset.target);
    if (!target || !window.html2canvas || !window.Plotly) return;
    btn.disabled = true;
    btn.dataset.label = btn.dataset.label || btn.textContent;
    btn.textContent = "Rendering…";
    try {
      var canvas = await render(target);
      var blob = await new Promise(function (resolve) { canvas.toBlob(resolve, "image/png"); });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = slug(btn.dataset.name) + "-" + fileStamp() + ".png";
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
      flash(btn, "Saved ✓");
    } catch (err) {
      console.error("[export] PNG export failed", err);
      flash(btn, "Export failed");
    }
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest && e.target.closest(".dl-btn");
    if (btn) handle(btn);
  });
})();
