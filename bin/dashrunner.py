# Limitations
# - When using the dashboard= argument, Does not work with private dashboards
# - When using the dashboard= argument, Does not work on dashboards shared from another app
# - Does not work on dashboard studio becuase dashboard studio dashboards are stupid
# - you need to set all tokens explicitly and cant rely on default tokens or tokens that are set by change handlers

# Features
# - each individual search can run for up to 10 mins, but this can be overridden using the dashrunner_X_maxwait token


import splunk.rest, splunk.search, json, time, traceback, re, pprint, sys
from collections import OrderedDict
import xml.etree.cElementTree as et
from urllib.parse import unquote, quote_plus
import splunk.Intersplunk

def dashrunner():
    dr = {
        "dashboards": "",
        "mode": "run",
        "id": "",
        "onDashboard": "",
        "logLocation": "",
        "testmode_log": [],
        "owner": None,
        "session_key": None,
        "max_dashboards": "1000"
    }

    # process args
    for i in range(1, len(sys.argv)):
        splitter = sys.argv[i].find('=')
        if splitter > 0:
            name = sys.argv[i][0:splitter]
            value = sys.argv[i][splitter+1:len(sys.argv[i])]
        if name == "dashboards":
            dr['dashboards'] = value
        if name == "id":
            dr['id'] = value.lower()
        if name == "mode":
            dr['mode'] = value.lower()

    if not (dr['mode'] == "run" or dr['mode'] == "validate" or dr['mode'] == "test"):
        splunk.Intersplunk.parseError("mode=\"\" argument must be (test,validate,run)")
    if dr['id'] is None or dr['id'] == "":
        splunk.Intersplunk.parseError("must be run with id=\"\" argument. For documentation go to https://splunkbase.splunk.com/app/7397")

    def log_info(message):
        dr['testmode_log'].append({"_time": time.time(), "log_level": "INFO", "object": dr['logLocation'], "message": message})

    def log_warning(message):
        if dr['mode'] != "validate":
            print("WARN [" + dr['logLocation'] + "] " + message, file=sys.stderr)
        dr['testmode_log'].append({"_time": time.time(), "log_level": "WARN", "object": dr['logLocation'], "message": message})

    def log_error(message):
        if dr['mode'] != "validate":
            print("ERROR [" + dr['logLocation'] + "] " + message, file=sys.stderr)
        dr['testmode_log'].append({"_time": time.time(), "log_level": "ERROR", "object": dr['logLocation'], "message": message})


    results, dummyresults, settings = splunk.Intersplunk.getOrganizedResults()
    dr['session_key'] = settings.get('sessionKey', None)
    dr['owner'] = settings.get('owner', None)


    def process_dashboard(appcontext, page_stem, dashboard_xml):
        #self.logger.debug("Processing dashboard xml (" + str(json.dumps(dashboard_xml)) + ")")

        group_ids = {}
        searches = {}
        dashboardresults = []

        root = et.fromstring(dashboard_xml)
        init_tokens = root.findall("./init/set[@token]")
        #log_info("Processing dashboard \"" + appcontext + "/" + page_stem + "\" found init tokens: " + str(len(init_tokens)))
        if len(init_tokens) == 0:
            log_info("Did not find any <init> tokens in dashboard \"" + appcontext + "/" + page_stem + "\"")
        tokensValid = {}
        tokensIgnored = {}
        for elem in init_tokens:
            val = ""
            if not elem.text is None:
                val = elem.text.strip()
            if elem.attrib['token'].startswith("dashrunner_"):
                token_name_parts = elem.attrib['token'][11:].split("_")
                group_id = token_name_parts[0]
                if not group_id in group_ids:
                    group_ids[group_id] = {
                        "id": "",  # mandatory
                        "searchid": "", # optional
                        "tokens": "", # optional
                        "postprocess": "", # optional
                        "earliest": "-1s", # optional
                        "latest": "now", # optional
                        "maxwait": 600, # optional, in seconds
                        "pause": 1, # optional, in seconds, time to sleep/pause after running the dashboard
                        "namespace": appcontext, # optional - defaults to app where the dashboard lives
                        "_seen": {}
                    }
                if not token_name_parts[1] in group_ids[group_id]:
                    log_warning("Unknown token \"dashrunner_" + group_id + "_" + token_name_parts[1] + "\".")
                else: 
                    if elem.attrib['token'] in group_ids[group_id]["_seen"]:
                        log_warning("Token appears twice: \"dashrunner_" + group_id + "_" + token_name_parts[1] + "\".")
                    tokensValid[elem.attrib['token']] = val
                    group_ids[group_id]["_seen"][elem.attrib['token']] = val
                if token_name_parts[1] == "maxwait" or token_name_parts[1] == "pause":
                    if val.isdigit():
                        group_ids[group_id][token_name_parts[1]] = int(val)
                    elif val != "":
                        log_error("token '" + elem.attrib['token'] + "' is not an integer")
                else:
                    group_ids[group_id][token_name_parts[1]] = val
            else:
                tokensIgnored[elem.attrib['token']] = val
        if len(tokensValid) > 0:
            log_info("Tokens found:\n" + pprint.pformat(tokensValid, width=100))
        if len(tokensIgnored) > 0:
            log_info("Tokens ignored:\n" + pprint.pformat(tokensIgnored, width=100))

        # process the group now
        for group_id in group_ids:
            if dr['id'] != "*" and group_ids[group_id]["id"] == "":
                log_info("Skipping token group \"" + group_id + "\" becuase it does not have token 'dashrunner_" + group_id + "_id' or its blank.")
                continue
            
            if dr['id'] != "*" and group_ids[group_id]["id"] != dr['id']:
                log_info("Skipping token group \"" + group_id + "\" with different id=\"" + group_ids[group_id]["id"] + "\".")
                continue

            dr['logLocation'] = dr['onDashboard'] + ":" + group_id

            group_ids[group_id]["search_string"] = ""

            if group_ids[group_id]["searchid"] != "":
                group_ids[group_id]["earliest"] = ""
                group_ids[group_id]["latest"] = ""
                try:
                    group_ids[group_id]["search_string"], group_ids[group_id]["earliest"], group_ids[group_id]["latest"] = findSearchRecursivly(root, group_ids[group_id]["searchid"])
                except Exception:
                    log_error(str(ex))
                    continue

            # replace tokens used in the search by their values
            group_ids[group_id]["tokens_obj"] = parse_tokens(group_ids[group_id]["tokens"])
            # handle the $env:page$ token
            group_ids[group_id]["tokens_obj"]["env:page"] = page_stem
            # replace tokens 
            for item in ["search_string","earliest","latest","postprocess"]:
                for token in group_ids[group_id]["tokens_obj"]:
                    group_ids[group_id][item] = group_ids[group_id][item].replace("$" + token + "$", group_ids[group_id]["tokens_obj"][token]).replace("$" + token + "|s$", "\"" + group_ids[group_id]["tokens_obj"][token] + "\"")
            group_ids[group_id]["search_ref"] = group_ids[group_id]["searchid"] + " " + group_ids[group_id]["tokens"]

            # fix occurances of $$ which is how single dollar signs should be quoted
            group_ids[group_id]["search_string"] = group_ids[group_id]["search_string"].replace("$$","$")

            if group_ids[group_id]["postprocess"] != "" and not group_ids[group_id]["postprocess"].startswith("|"):
                group_ids[group_id]["postprocess"] = "| " + group_ids[group_id]["postprocess"]

        # this logic can be uncommented to deal with searches that have the same base search and tokens
        # TODO handle when there are two searches that can reuse the base search. need to run base search then use loadjob repeatedly.
        #     if not group_ids[group_id]["search_ref"] in searches:
        #         searches[ group_ids[group_id]["search_ref"] ] = {"count": 0, "usedby": {}}
        #     searches[ group_ids[group_id]["search_ref"] ]['count'] += 1
        #     searches[ group_ids[group_id]["search_ref"] ]['usedby'][group_id] = 1
        #     self.logger.info("final: " + str(group_ids[group_id]))
        # for search_ref in searches:
        #     if searches[search_ref]['count'] == 1:
        #         for group_id in searches[search_ref]['usedby']:
            try:
                sr = start_search(group_ids[group_id]["search_string"] + "\n\n" + group_ids[group_id]["postprocess"], group_ids[group_id]["earliest"], group_ids[group_id]["latest"], group_ids[group_id]["namespace"], group_ids[group_id]["maxwait"])
                
                if dr['mode'] == "test":
                    fieldlist = []
                    if len(sr["results"]) > 0:
                        for column in sr["results"][0]:
                            fieldlist.append(column)
                    test_results = {
                        "app": appcontext,
                        "dashboard": page_stem,
                        "groupid": group_id,
                        "maxwait": str(group_ids[group_id]["maxwait"]),
                        "run_duration_sec": str(round(sr["duration"])),
                        "results": str(len(sr["results"])),
                        "messages": "\n".join(map(str, sr["messages"])),
                        "fields": str(fieldlist),
                        "job_sid": sr["sid"]
                    }
                    dashboardresults.append(test_results)
                else:
                    # Add some extra fields to the results so that its possible to understand where the results came form
                    for row in sr["results"]:
                        row["dashrunner_app"] = appcontext
                        row["dashrunner_dashboard"] = page_stem
                        row["dashrunner_groupid"] = group_id
                    # append results to result set for any other searches on this dashboard
                    dashboardresults += sr["results"]
            except Exception as ex:
                log_error("problem running search: " + str(ex))

            # pause between searches
            if group_ids[group_id]["pause"] > 0:
                time.sleep(group_ids[group_id]["pause"])
        return dashboardresults

    def findSearchRecursivly(root, searchId):
        querystring = ""
        earliest = ""
        latest = "now"
        searchcandidtes = root.findall(".//search[@id='" + searchId + "']")
        foundcount = len(searchcandidtes)
        if foundcount == 0:
            raise Exception("could not find search with id=\"" + searchId + "\"")
        elif foundcount > 1:
            raise Exception("found too many (" + str(foundcount) + ") searches with id=\"" + searchId + "\"")
        else:
            #self.logger.debug("found search code: " + searchcandidtes[0].find("query").text)
            querystring = searchcandidtes[0].find("query").text
            querystring = querystring.strip()

            if "base" in searchcandidtes[0].attrib:
                # need to recurse
                #self.logger.debug("search uses a base search: " + searchcandidtes[0].attrib['base'])
                q, earliest, latest = findSearchRecursivly(root, searchcandidtes[0].attrib['base'])
                if not querystring.startswith("|"):
                    querystring = "| " + querystring
                querystring = q + "\n" + querystring
            else:
                # these can be blank
                earliest = searchcandidtes[0].find("earliest")
                if earliest is None:
                    log_warning("Search with id=\"" + searchId + "\" does not have an <earliest> time. Will default to blank.")
                    earliest=""
                else:
                    earliest = earliest.text
                latest = searchcandidtes[0].find("latest")
                if latest is None:
                    log_warning("Search with id=\"" + searchId + "\" does not have an <latest> time. Will default to blank.")
                    latest=""
                else:
                    latest = latest.text
            return querystring, earliest, latest

    def parse_tokens(url):
        # Decode the URL in case it's encoded
        url = unquote(url)
        if isinstance(url, str):
            # Split the query string by ampersand (&)
            params_list = url.split('&')
            params = {}
            # Iterate over each key-value pair in the list
            for param in params_list:
                if len(param) > 0:
                    # Split the key-value pair at the equal sign (=)
                    key, value = param.split('=', 1)
                    # Add the key-value pair to the dictionary
                    params[key] = value
                    # users may sometimes say the tokens are form.XXX so we will replace these as well.
                    if key.startswith("form."):
                        params[key[5:]] = value
            return params
        else:
            return {}  # Return empty dictionary if not a string

    def start_search(searchQuery, earliest, latest, namespace, maxwait):
        ret = {"sid":"", "duration":0, "results":[], "messages":[]}
        # Remove leading and trailing whitespace from the search
        searchQuery = searchQuery.strip()

        if len(searchQuery) == 0:
            log_error("Search is empty. Make sure dashrunner_*_searchid and/or dashrunner_*_postprocess tokens are set properly.")
            return ret
        # If the query doesn't already start with the 'search' operator or another
        # generating command (e.g. "| inputcsv"), then prepend "search " to it.
        if not (searchQuery.startswith('search') or searchQuery.startswith("|")):
            searchQuery = 'search ' + searchQuery
        log_info("Search constructed (earliest=" + earliest + " latest=" + latest + " namespace=" + namespace + " maxwait="+ str(maxwait) + "seconds):\n\n" + searchQuery )

        # warn if there seem to be any tokens left.
        possible_tokens = re.findall(r"\$.*?\$", searchQuery + "\n" + earliest + "\n" + latest)
        for t in possible_tokens:
            log_warning("Detected potentially unset token \"" + t + "\" in search string.")

        # Parse the search using the parser endpoint.
        if dr['mode'] == "validate":
            baseurl = '/servicesNS/' + dr['owner'] + '/' + namespace + '/search/v2/parser'
            try:
                response, content = splunk.rest.simpleRequest(baseurl + '?output_mode=json', sessionKey=dr['session_key'], postargs={'q':searchQuery}, method='POST')
                if response.status != 200:
                    log_warning("Parse check of search failed: " + json.loads(content)["messages"][0]["text"])
            except Exception:
                #log_warning("Parse check of search failed: unexpected " + str(content))
                # this can sometimes fail becuase parsing large queries takes a long time. its not super important so just ignore
                pass
            return ret
        search_start_time = time.time()
        baseurl = '/servicesNS/' + dr['owner'] + '/' + namespace + '/search/jobs'
        response, content = splunk.rest.simpleRequest(baseurl + '?output_mode=json', sessionKey=dr['session_key'], postargs={'search':searchQuery, 'earliest_time': earliest, 'latest_time': latest}, method='POST', rawResult=True)
        if response.status == 400:
            try:
                log_error("search job failed becuase: " + json.loads(content)["messages"][0]["text"])
                return ret
            except Exception:
                log_error("search job failed becuase: " + content)
                return ret
        if response.status != 201:
            log_error("submitting search job returned an unexpected status (" + str(response.status) + ") - expected 201, when submitting search job (" + str(content) + ")")
            return ret
        try:
            ret["sid"] = json.loads(content)['sid']
        except Exception:
            log_error("search job failed becuase count not decode SID in response: " + content)
            return ret
        #self.logger.info("Job sid is (" + str(sid) + ")")
        while True:
            # poll every second to see if job is completed
            response, content = splunk.rest.simpleRequest(baseurl + '/' + str(ret["sid"]) + '/results?output_mode=json', sessionKey=dr['session_key'], rawResult=True)
            ret["duration"] = time.time() - search_start_time
            if response.status == 200:
                # got results 
                try:
                    retObj = json.loads(content)
                    ret['messages'] = retObj["messages"]
                    ret['results'] = retObj["results"]
                    return ret
                except Exception:
                    log_error("Could not read results from search content: " + content)
                    return ret
            elif response.status == 204:
                # results still coming
                if ret["duration"] > maxwait:
                    log_error("search job took too long to run and will be cancelled (maxwait is " + str(maxwait) + "sec and can be overridden using the dashrunner_X_maxwait token")
                    # finalise the job now. instead of cancel, we finalise, but we dont use the results anyway. cancel doesnt seem to actually cancel.
                    del_response, del_content = splunk.rest.simpleRequest(baseurl + '/' + str(ret["sid"]) + '/control?output_mode=json', sessionKey=dr['session_key'], postargs={'action':'finalize'}, method='POST', rawResult=True)
                    if del_response.status != 200:
                        log_warning("canceling search job returned unexpected status code (" + str(del_response.status) + "with content (" + str(del_content) + ")")
                    return ret
                time.sleep(1)
            else:
                log_error("unexpected status \"" + str(response.status) + "\" when checking for job completion (expected 200 or 204), response=\"" + str(content) + "\"")
                return ret

    finalresults = []
    if dr['dashboards'] is "":
        log_info("The dashboard= argument was not set. Will query for all dashboards that contain the string: \"dashrunner*id*" + quote_plus(dr['id']) + "\" | rest splunk_server=local /servicesNS/-/-/data/ui/views f=\"eai:data\" search=\"dashrunner*id*" + quote_plus(dr['id']) + "\" count=\"" + dr['max_dashboards'] + "\"")
        try:
            response, content = splunk.rest.simpleRequest("/servicesNS/-/-/data/ui/views?output_mode=json&count=" + dr['max_dashboards'] + "&search=%22dashrunner*" + quote_plus(dr['id']) + "%22", sessionKey=dr['session_key'], rawResult=True)
            #self.logger.debug("Returned status (" + str(response.status) + ")")
            #self.logger.debug("Returned content (" + str(content) + ")")
            if response.status != 200:
                log_error("unexpected response code (" + str(response.status) + ") when querying for all dashboards.")
            else:
                dashboards_json = json.loads(content)
                if len(dashboards_json['entry']) == 0:
                    log_error("No dashboards found. Check that ID is correct.")
                else:
                    log_info("Dashboards matched: " + str(len(dashboards_json['entry'])))
                    for dashboard_obj in dashboards_json['entry']:
                        dr['onDashboard'] = dashboard_obj['acl']['app'] + "/" + dashboard_obj['name']
                        dr['logLocation'] = dr['onDashboard']
                        finalresults += process_dashboard(dashboard_obj['acl']['app'], dashboard_obj['name'], dashboard_obj['content']['eai:data'])
        except json.JSONDecodeError as ex:
            log_error("unable to parse json of all dashboards " + str(ex))
        except Exception as ex:
            log_error("unexpected error " + str(ex))

    else:
        for dashboard_simplepath in dr['dashboards'].split(","):
            dashboard_simplepath = dashboard_simplepath.strip()
            # if there is a leading slash, remove it
            if dashboard_simplepath.startswith("/"):
                    dashboard_simplepath = dashboard_simplepath[1:]
            dashboard_parts = dashboard_simplepath.split("/")
            if len(dashboard_parts) != 2:
                log_error("unexpected dashboard path \"" + dashboard_simplepath + "\", expected \"app_context/dashboard_url\"")
                continue
            dr['onDashboard'] = dashboard_simplepath
            dr['logLocation'] = dr['onDashboard']
            dashboard_url = '/servicesNS/nobody/' + dashboard_parts[0] + '/data/ui/views/' + dashboard_parts[1] + '?output_mode=json&f=eai:data'
            log_info("Specified dashboard \"" + dashboard_simplepath + "\" will be retreived from endpoint \"" + dashboard_url + "\"")
            try:
                response, content = splunk.rest.simpleRequest(dashboard_url, sessionKey=dr['session_key'], rawResult=True)
                #self.logger.debug("Returned status (" + str(response.status) + ")")
                #self.logger.debug("Returned content (" + str(content) + ")")
                if response.status != 200:
                    log_error("unexpected response code (" + str(response.status) + ") when querying for dashboard. Make sure the dashboard is not private and that it exists in this app context (not just shared into it)")
                else:
                    dashboard_json = json.loads(content)
                    finalresults += process_dashboard(dashboard_parts[0], dashboard_parts[1], dashboard_json['entry'][0]['content']['eai:data'])
            except json.JSONDecodeError as ex:
                log_error("unable to parse json of dashboard " + str(ex))
            except Exception as ex:
                log_error("Make sure the dashboard is not private and that it exists in this app context (not just shared into it) (" + str(ex) + ")")

    if dr['mode'] == "validate":
        splunk.Intersplunk.outputResults(dr['testmode_log'])
    else:
        splunk.Intersplunk.outputResults(finalresults)

if __name__ == '__main__':
    dashrunner()
