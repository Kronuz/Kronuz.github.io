---
title:      First Post
date:       2015-04-09 10:20:00 -0600
modified:   2015-04-23 14:00:00 -0600
categories: Blogging
author:     Kronuz
tags:       pelican
identifier: first-post
redirect_from: /first-post.html
---

This is my first post using Pelican.

I've recently started a new blog using Pelican.

To install Pelican I used `pip install pelican markdown ghp-import`,
then I created a new directory and used `pelican-quickstart` to setup
the new directory with the pelican project.

Added a script for publishing `publish.sh`:

```bash
#!/bin/sh

pelican content -o published -s publishconf.py && \
ghp-import -b master published && \
git push origin master
```

Added a hook to `.git/hooks/post-commit`:

```sh
~ $ sh publish.sh
```

Don't forget to set execution permissions to the scripts:

```sh
~ $ chmod +x publish.sh
~ $ chmod +x .git/hooks/post-commit
```

It was really easy to setup, now with every commit, the blog gets
published!
