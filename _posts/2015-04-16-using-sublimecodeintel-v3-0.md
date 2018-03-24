---
title:      SublimeCodeIntel v3.0
date:       2015-04-16 14:20:00 -0600
modified:   2017-09-06 11:30:00 -0600
category:   Sublime Text
author:     Kronuz
tags:       codeintel, komodo, sublime, sublimetext, sublimecodeintel
identifier: using-sublimecodeintel-v30
---

Installing SublimeCodeIntel v3.0.

Lately I've been working on a new python package: CodeIntel

Python package CodeIntel (<https://pypi.python.org/pypi/CodeIntel>), for
using with Sublime Text and SublimeCodeIntel v3.0.

To install you need a working Python and pip:

```sh
pip install -U --pre codeintel
```

If it all goes well, congratulations, you can now upgrade to and use
SublimeCodeIntel v3.0 beta.

Having accepted than SublimeCodeIntel v3.0 is yet a beta release, and if
you are willing and ready to try it out, follow the next steps to
upgrade:

1.  **Make sure you have properly installed CodeIntel package before
    proceeding, it's a requirement**
2.  In Sublime Text, go to
    `Preferences > Package Settings > Package Control > Settings - User`
    and add SublimeCodeIntel to the list of prereleases:

    ```json
    "install_prereleases": ["SublimeCodeIntel"],
    ```

3.  Run the *Package Control: Upgrade Package* command from the command
    palette and select `SublimeCodeIntel` (note it should say there
    it's v3.0).
4.  Restart Sublime Text when it's done upgrading.
