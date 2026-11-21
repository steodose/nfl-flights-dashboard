/*
 * Keeps city labels visible on the route map.
 *
 * figures.py already places each label on a free side of its dot, but MapLibre still hides
 * labels it judges too close. Allow overlap at the fitted zoom and closer; when zoomed further
 * out, where labels really would collide, let MapLibre thin them again.
 *
 * Plotly rebuilds the map layers on every update, so this re-checks them on a short timer.
 */
(function () {
  function apply(gd) {
    var sub = gd._fullLayout && gd._fullLayout.map && gd._fullLayout.map._subplot;
    var map = sub && sub.map;
    if (!map || !map.isStyleLoaded() || !gd.layout.map) return;
    var keep = map.getZoom() >= (gd.layout.map.zoom || 0) - 0.25;
    (gd._fullData || []).forEach(function (trace) {
      if (trace.mode !== "markers+text") return;
      var id = "plotly-trace-layer-" + trace.uid + "-symbol";
      if (map.getLayer(id) && !!map.getLayoutProperty(id, "text-allow-overlap") !== keep) {
        map.setLayoutProperty(id, "text-allow-overlap", keep);
      }
    });
  }

  setInterval(function () {
    var gd = document.querySelector("#map .js-plotly-plot");
    if (gd) apply(gd);
  }, 300);
})();
