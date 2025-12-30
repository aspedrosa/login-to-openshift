# Login To Openshift in one command

Command-line tool to log in to an OpenShift Kubernetes cluster without using the web console, directly retrieving the
login token so you can use `kubectl` or `oc` commands.

## Requirements

- oc binary installed

## Build binary

1. Create python virtual environment
2. Install requirements
   ```bash
   pip install -r requirements.txt
   ```
3. Run build script
   ```bash
   ./build.sh --username <username> --base-url <base-url>
   ```
   Both of these options are optional.

   If username is not provided, script will prompt for it.

   If base url is not provided, a default value (my company's openshift URL) will be used.

   Both of these options can be provided as environment variables (OPENSHIFT_USERNAME and OPENSHIFT_BASE_URL)
