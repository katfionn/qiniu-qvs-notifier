# GitHub Actions Permissions Fix

If you are seeing an error like this in your GitHub Actions tab:

> `Error: The actions actions/checkout@v4, docker/setup-qemu-action@v3, docker/setup-buildx-action@v3, docker/login-action@v3, docker/metadata-action@v5, and 1 other are not allowed in katfionn/Qiniu-QVS-device-alert-to-Dingtalk-bot- because all actions must be from a repository owned by katfionn.`

**This is a GitHub repository settings issue, not a code issue.**

To fix this:

1. Go to your repository on GitHub.
2. Click on **Settings** (the gear icon).
3. On the left sidebar, expand **Actions** and click **General**.
4. Scroll down to the **Actions permissions** section.
5. Select **"Allow all actions and reusable workflows"**.
   - *(Alternatively, select "Allow katfionn, and select non-katfionn, actions and reusable workflows" and check the box below it to allow actions created by GitHub).*
6. Click **Save** at the bottom of that section.
7. Go back to the **Actions** tab and re-run your failed workflow.
