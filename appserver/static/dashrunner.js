
require([
    'jquery',
    'splunkjs/mvc',
    'splunkjs/mvc/simplexml/ready!'
], function($, mvc) {
    setTimeout(function(){
        // Uncomment/alter this code if you would like to control who sees the "dashrunner" button
        //if (Splunk.util.getConfigValue("USERNAME") !== "admin") {
        //    return;
        //}
        var hasDashrunner = false;
        var dashRunnerIDs = {};
        var id = "";
        var str = "";
        var dashboard_id = "dashboard1";
        for(var tok in splunkjs.mvc.Components.attributes){
            if (splunkjs.mvc.Components.attributes.hasOwnProperty(tok)) {
                if (splunkjs.mvc.Components.attributes[tok].hasOwnProperty("options") && splunkjs.mvc.Components.attributes[tok].options.hasOwnProperty("isDashboard") && splunkjs.mvc.Components.attributes[tok].options.isDashboard) {
                    dashboard_id = tok;
                }
            }
        }
        for (var tok in mvc.Components.attributes.submitted.attributes){
            if (mvc.Components.attributes.submitted.attributes.hasOwnProperty(tok) && tok.substr(0,11) === "dashrunner_"){
                id = tok.substr(11).replace(/.*?_/,"");
                if (id === "id") {
                    dashRunnerIDs[ mvc.Components.attributes.submitted.attributes[tok] ] = 1;
                }
                hasDashrunner = true;
            }
        }
        var dashboardRealLocation = splunkjs.mvc.Components.attributes[dashboard_id].model.view.id.replace("/servicesNS/", "").replace("data/ui/views/","");
        var dashboardRealApp = dashboardRealLocation.replace(/^[^\/]*\//,"").replace(/\/.*/,"");
        var dashboardRealFile = dashboardRealLocation.replace(/^[^\/]*\/[^\/]*\//,"");
        for (id in dashRunnerIDs) {
            if (dashRunnerIDs.hasOwnProperty(id)) {
                str += "<li><strong>" + id + "</strong> <a target='_blank' href='search?q=%7Cdashrunner%20id%3D&quot;" + id + "&quot;%20dashboards%3D&quot;" + dashboardRealApp + "%2F" + dashboardRealFile + "&quot;%20mode%3D&quot;validate&quot;'>Validate</a> | <a target='_blank' href='search?q=%7Cdashrunner%20id%3D&quot;" + id + "&quot;%20dashboards%3D&quot;" + dashboardRealApp + "%2F" + dashboardRealFile + "&quot;%20mode%3D&quot;test&quot;'>Test</a> | <a target='_blank' href='search?q=%7Cdashrunner%20id%3D&quot;" + id + "&quot;%20dashboards%3D&quot;" + dashboardRealApp + "%2F" + dashboardRealFile + "&quot;'>Run</a></li>" 
            }
        }
        if (hasDashrunner) {
            $('<button class="btn dashrunner-button" style="margin-right: 6px;"><span style="margin: 0 8px 0 0; font-size: 19px; transform: translateY(2px); display: inline-block;" class="icon-clock"></span><span>Dashrunner</span></button>').on("click", function(){
                var $modal = $('<div class="modal fade" style="width: 600px; margin-left: -300px;" id="help_modal" tabindex="-1" role="dialog" aria-labelledby="modalChartLabel" aria-hidden="true">'+
                    '<div class="modal-dialog" role="document">'+
                    '<div class="modal-content">'+
                        '<div class="modal-header">'+
                        '<h5 class="modal-title" id="modalChartLabel">Dashrunner tokens</h5>'+
                        '<button type="button" class="close" data-dismiss="modal" aria-label="Close"></button>'+
                        '</div>'+
                        '<div class="modal-body" style="overflow:auto;"><br /><ul>' + str + '</ul></div>' +
                        '<div class="modal-footer">'+
                            '<button type="button" class="btn btn-primary" data-dismiss="modal">Close</button>'+
                        '</div>'+
                    '</div>'+
                    '</div>'+
                '</div>');
                $modal.find(".model_injected_content").html();
                $modal.modal();
            }).prependTo(".dashboard-view-controls");
        }
    // wait 1 second before running
    },1000);
});