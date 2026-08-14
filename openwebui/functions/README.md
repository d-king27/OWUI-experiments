# Functions and adapters

Future Open WebUI Pipe Functions or other adapters will live here under source control.

The likely request path is:

```text
User
  |
  v
Open WebUI
  |
  v
How-To Agent adapter
  |
  v
HowToAgent domain logic
  +-- process definition
  +-- knowledge
  +-- future tools and APIs
  |
  v
LLM
```

The adapter should translate Open WebUI requests and responses while delegating process behavior to the agent package.

## Security

Open WebUI Functions execute server-side Python with the privileges of the Open WebUI process. Do not install arbitrary community Functions, download executable plugins at startup, or hard-code credentials. Review and source control every extension introduced here.
