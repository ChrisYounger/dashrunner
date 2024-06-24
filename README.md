Dashrunner is a custom command that will parse SimpleXML dashboards, extract searches (based on configurable tokens) and run those searches.

Do you have a simple XML dashboard where you want the dashboard results sent via email/slack/etc regularly?
Do you wish that a dashboard's results could be summarised and tracked over time?

Typically you need to copy the search logic into saved searches to accomplish these goals. Duplicating the logic creates extra maintenance and is error-prone because it does not follow the DRY (Don't repeat yourself https://en.wikipedia.org/wiki/Don%27t_repeat_yourself) principle of software development. You could reach for a macro (or similar) to store search logic, however, now you have logic in numerous places and it's still difficult to maintain.

With Dashrunner you can now store all the logic in one place, inside the dashboard, using hidden tokens. You will still need one or more saved searches, but these are now generic "runners" that typically contain only simple action logic.


Copyright (C) 2024 Chris Younger | [Splunkbase](https://splunkbase.splunk.com/app/7397) | [Source code](https://github.com/ChrisYounger/dashrunner) | [My Splunk apps](https://splunkbase.splunk.com/apps/#/author/chrisyoungerjds)
