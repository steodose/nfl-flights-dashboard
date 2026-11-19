var dagcomponentfuncs = (window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {});

// Opponent cell: team helmet + name.
dagcomponentfuncs.TeamHelmet = function (props) {
  var helmet = props.data && props.data.home_helmet;
  return React.createElement(
    "span",
    { className: "team-cell" },
    helmet
      ? React.createElement("img", { src: helmet, alt: "", className: "helmet", loading: "lazy" })
      : null,
    React.createElement("span", null, props.value)
  );
};
