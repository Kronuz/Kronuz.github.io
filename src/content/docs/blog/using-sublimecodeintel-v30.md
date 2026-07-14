---
title: "SublimeCodeIntel v3.0"
description: "How to install and upgrade to SublimeCodeIntel v3.0 beta, now built on the standalone CodeIntel Python package (pip install codeintel)."
excerpt: "SublimeCodeIntel v3.0 splits the engine into a standalone CodeIntel Python package. Here is how to install the pip package and upgrade Sublime Text to the v3.0 beta."
date: 2015-04-16
draft: true
authors: kronuz
tags:
  - codeintel
  - komodo
  - sublime
  - sublimetext
  - sublimecodeintel
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
