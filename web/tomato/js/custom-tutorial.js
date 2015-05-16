function customTutorial() {
	var dialog = $("<div/>");
	var ta = $('<input type="text" name="tutorial_url" style="width: 100%" />');
	dialog.append(ta);
	var t = this;
	dialog.dialog({
		autoOpen: true,
		draggable: true,
		resizable: false,
		height: "auto",
		width: 400,
//		title: gettext("Tutorial URL"),
		title: gettext("Tutorial URL"),
		show: "slide",
		hide: "slide",
		modal: true,
		buttons: {
			Open: function() {
				dialog.dialog("close");
			//	window.location = "{%url "tutorial.start" %}?url="+ta.val();
				window.location = "/tutorial/start?url="+ta.val();
			},
			Cancel: function() {
				dialog.dialog("close");
			}
		},
	});
}

