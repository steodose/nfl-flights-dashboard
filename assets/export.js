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

  // ---- Safari-safe chart rasterisation -------------------------------------------------
  // Safari drops external <image>s and web fonts when Plotly turns its SVG into a PNG, and
  // returns a blank WebGL map. So: inline layout images and the Titillium font as data URIs,
  // rasterise the SVG ourselves, and copy maps straight from their live canvas.

  var dataUrlCache = {};
  function toDataUrl(url) {
    if (!url || url.indexOf("data:") === 0) return Promise.resolve(url);
    if (!dataUrlCache[url]) {
      dataUrlCache[url] = fetch(url).then(function (r) { return r.blob(); }).then(function (b) {
        return new Promise(function (resolve) {
          var fr = new FileReader();
          fr.onload = function () { resolve(fr.result); };
          fr.readAsDataURL(b);
        });
      }).catch(function () { return url; });
    }
    return dataUrlCache[url];
  }

  var fontCss = null;
  function embeddedFontCss() {
    if (!fontCss) {
      var href = Array.prototype.map.call(document.querySelectorAll('link[rel="stylesheet"]'), function (l) { return l.href; })
        .filter(function (h) { return h.indexOf("fonts.googleapis.com") !== -1; })[0];
      fontCss = !href ? Promise.resolve("") : fetch(href).then(function (r) { return r.text(); }).then(function (css) {
        // Keep the latin faces only; inline each font file.
        var blocks = css.split("/* ").filter(function (b) { return b.indexOf("latin */") === 0; });
        return Promise.all(blocks.map(function (b) {
          var face = b.slice(b.indexOf("@font-face"));
          var m = face.match(/url\(([^)]+)\)/);
          return m ? toDataUrl(m[1]).then(function (d) { return face.replace(m[1], d); }) : face;
        })).then(function (faces) { return faces.join("\n"); });
      }).catch(function () { return ""; });
    }
    return fontCss;
  }

  function mapCanvas(gd) {
    var fl = gd._fullLayout || {};
    var sub = (fl.map && fl.map._subplot) || (fl.mapbox && fl.mapbox._subplot);
    return sub && sub.map;
  }

  function captureMap(map) {
    // Read the WebGL canvas inside a render frame, before the buffer is cleared.
    var hiDpi = map.setPixelRatio && map.getPixelRatio && map.getPixelRatio() < SCALE;
    var prev = hiDpi ? map.getPixelRatio() : null;
    if (hiDpi) map.setPixelRatio(SCALE);
    return new Promise(function (resolve) {
      // Wait for tiles at the new resolution, then grab the frame.
      map.once("idle", function () {
        map.once("render", function () {
          var url = map.getCanvas().toDataURL("image/png");
          if (hiDpi) map.setPixelRatio(prev);
          resolve(url);
        });
        map.triggerRepaint();
      });
      map.triggerRepaint();
    }).then(loadImage);
  }

  async function chartImage(gd) {
    var map = mapCanvas(gd);
    if (map) return captureMap(map);
    var w = gd.offsetWidth, h = gd.offsetHeight;
    var layout = Object.assign({}, gd.layout, { width: w, height: h });
    layout.images = await Promise.all((gd.layout.images || []).map(function (im) {
      return toDataUrl(im.source).then(function (src) { return Object.assign({}, im, { source: src }); });
    }));
    var svgUrl = await window.Plotly.toImage({ data: gd.data, layout: layout, config: { staticPlot: true } },
      { format: "svg", width: w, height: h });
    var body = svgUrl.slice(svgUrl.indexOf(",") + 1);
    var svg = svgUrl.indexOf(";base64,") !== -1 ? atob(body) : decodeURIComponent(body);
    var css = await embeddedFontCss();
    if (css) svg = svg.replace(/(<svg[^>]*>)/, "$1<style>" + css + "</style>");
    var img = await loadImage("data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg));
    // Safari fires onload before images/fonts nested in the SVG have decoded; give them a
    // moment (attached off-screen so WebKit actually decodes) before drawing.
    img.style.cssText = "position:fixed;left:-99999px;top:0;width:" + w + "px;height:" + h + "px;";
    document.body.appendChild(img);
    try { if (img.decode) await img.decode(); } catch (e) { /* ignore */ }
    await new Promise(function (r) { setTimeout(r, 400); });
    var c = document.createElement("canvas");
    c.width = w * SCALE; c.height = h * SCALE;
    c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
    img.remove();
    return c;
  }

  // html2canvas renders from a cloned copy of the page in a hidden iframe and waits for that
  // iframe's load event. On the deployed site Safari sometimes leaves the clone stuck at
  // readyState "interactive" even though every resource has loaded, so the export hangs.
  // If the clone stalls, nudge it: report "complete" and fire the load handler ourselves.
  function watchClone() {
    var seen = null, since = 0, kicked = false;
    var timer = setInterval(function () {
      var f = document.querySelector("iframe.html2canvas-container");
      if (!f || kicked) return;
      var d, w;
      try { d = f.contentDocument; w = f.contentWindow; } catch (e) { return; }
      if (!d || d.readyState === "complete" || !d.body || !d.body.childNodes.length) return;
      if (seen !== f) { seen = f; since = Date.now(); return; }
      if (Date.now() - since < 1500) return;
      var handler = w.onload || f.onload;
      if (typeof handler !== "function") return;
      kicked = true;
      try { Object.defineProperty(d, "readyState", { configurable: true, get: function () { return "complete"; } }); } catch (e) { /* ignore */ }
      handler.call(w);
    }, 250);
    return function () { clearInterval(timer); };
  }

  async function render(target) {
    var plots = Array.prototype.slice.call(target.querySelectorAll(".js-plotly-plot"));
    var images = await Promise.all(plots.map(chartImage));
    // Filled in from the html2canvas clone, whose layout differs from the live page
    // (ignored elements removed, scroll boxes expanded).
    var placements = [];

    var mutedColor = (getComputedStyle(document.documentElement).getPropertyValue("--muted") || "#8a8984").trim();

    var stopWatch = watchClone();
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
    }).finally(stopWatch);

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
