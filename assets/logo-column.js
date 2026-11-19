/*
 * Pins bar-chart logo columns to a fixed pixel offset from the figure's left edge.
 *
 * Plotly positions layout images in fractions of the plot width, so a fixed-pixel
 * column has to be recomputed whenever the plot's width changes. Figures opt in via
 * layout.meta = {logo_px, logo_left_px | logo_axis_gap_px} (see figures._logo_label_column).
 */
(function () {
  function pin(gd) {
    var meta = gd.layout && gd.layout.meta;
    var size = gd._fullLayout && gd._fullLayout._size;
    var images = (gd.layout && gd.layout.images) || [];
    if (!meta || meta.logo_px == null || !size || !size.w || !images.length) return;

    var x;
    if (meta.logo_left_px != null) {
      // Logo column pinned to the figure's left edge (images anchored left).
      x = -(size.l - meta.logo_left_px) / size.w;
    } else if (meta.logo_axis_gap_px != null) {
      // Logo column pinned just left of the axis (images anchored right).
      x = -meta.logo_axis_gap_px / size.w;
    } else {
      return;
    }
    var sizex = meta.logo_px / size.w;
    if (Math.abs(images[0].x - x) < 1e-4 && Math.abs(images[0].sizex - sizex) < 1e-4) return;

    var update = {};
    for (var i = 0; i < images.length; i++) {
      update["images[" + i + "].x"] = x;
      update["images[" + i + "].sizex"] = sizex;
    }
    window.Plotly.relayout(gd, update);
  }

  function hookAll() {
    document.querySelectorAll(".js-plotly-plot").forEach(function (gd) {
      if (!gd.__logoColumnHooked && typeof gd.on === "function") {
        gd.__logoColumnHooked = true;
        gd.on("plotly_afterplot", function () { pin(gd); });
      }
      pin(gd);
    });
  }

  // Dash mounts graphs asynchronously; a light poll catches new ones.
  setInterval(hookAll, 500);
})();
