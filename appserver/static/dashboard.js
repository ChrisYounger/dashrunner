require([
    'jquery',
    'splunkjs/mvc',
    'splunkjs/mvc/tableview',
    'splunkjs/mvc/simplexml/ready!'
], function($, mvc, TableView) {
    var submittedTokenModel = mvc.Components.get('submitted');
    // From the "Splunk Dashboard Examples" app
    $(document).on('click', '[data-set-token],[data-unset-token],[data-token-json]', function(e) {
        e.preventDefault();
        var target = $(e.currentTarget);
        var setTokenName = target.attr('data-set-token');
        if (setTokenName) {
            submittedTokenModel.set(setTokenName, target.attr('data-value'));
        }
        var unsetTokenName = target.attr('data-unset-token');
        if (unsetTokenName) {
            submittedTokenModel.unset(unsetTokenName);
        }
        var tokenJson = target.attr('data-token-json');
        if (tokenJson) {
            try {
                tokenJson = JSON.parse(tokenJson);
                if (typeof tokenJson === 'object' && ! Array.isArray(tokenJson) && tokenJson !== null) {
                    for (var key in tokenJson) {
                        if (tokenJson.hasOwnProperty(key)) {
                            if (tokenJson[key] === null) {
                                // Unset the token
                                submittedTokenModel.unset(key);
                            } else {
                                submittedTokenModel.set(key, tokenJson[key]);
                            }
                        }
                    }
                } else {
                    console.log("error parsing data-token-json, it might not be a valid object: ", tokenJson);
                }
            } catch(err) {
                console.warn("Cannot parse token JSON: ", err);
            }
        }
    });
    var DashrunnerTableRenderer = TableView.BaseCellRenderer.extend({
        canRender: function(cell) {
            return cell.value && typeof cell.value === "string" && cell.value.substr(0,5) === "html:";
        },
        render: function($td, cell) {
            var type = cell.value.substr(0,5);
            var content = cell.value.substr(5);
            if (type === "html:") {
                $td.html( content );
            }
        }
    });
    $("div.dashboard-element.table").each(function(){
        var id = $(this).attr("id");
        if (id.indexOf("dashrunner_table") > -1) {
            mvc.Components.get(id).getVisualization(function(tableView){
                tableView.addCellRenderer(new DashrunnerTableRenderer());
                tableView.render();
            });
        }
    });
});
