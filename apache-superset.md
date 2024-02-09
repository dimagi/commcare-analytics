Dimagi Superset Fork
--------------------

[Dimagi Superset](https://github.com/dimagi/hq_superset) is a fork of
[Apache Superset](https://github.com/apache/superset). Dimagi Superset
is maintained to build a slightly customized version of the
[Apache Superset PyPI package](https://pypi.org/project/apache-superset/).


### Making changes

We build most of the customization and integration inside this
[HQ Superset](https://github.com/dimagi/hq_superset) repo, and avoid
customizing Dimagi Superset, so that it diverges as little as possible
from Apache Superset. But we do customize Dimagi Superset when it's
very complicated or impossible to do inside HQ Superset.

In this spirit, 
- if the change is specific to CommCare HQ, try to implement the
  customization in [HQ Superset](https://github.com/dimagi/hq_superset).
- If the change is not specific to CommCare HQ and is useful to outside
  users, try to create a pull request against the upstream
  [Apache Superset](https://github.com/apache/superset) repo.
- If that is too complicated, you may have to add a change to the
  [Dimagi Superset](https://github.com/dimagi/superset) repo.

To include your changes in
[HQ Superset](https://github.com/dimagi/hq_superset) you will need to
track it under a proper Git release tag, build a new PyPI release from
your changes, and reference that release in HQ Superset's requirements.
The sections below explain how to do this.

### Keeping track of your changes via Git tags

Please note that maintaining Dimagi Superset in sync with upstream
changes, with our own customizations, and maintaining proper PyPI
versions (also the Git tags) is very difficult.

The [Apache Superset](https://github.com/apache/superset) repo maintains
Git tags to indicate the version of each released Superset PyPI
package. For example, see the
[1.4.1 release](https://github.com/apache/superset/releases/tag/1.4.1).
We follow the simple conventions below to maintain a patched version of the package that we can use in
[HQ Superset](https://github.com/dimagi/hq_superset).

- All our patches/customizations are done against an upstream release
  tag. We release only these patched versions of the upstream
  versions.

- By convention, these releases are tracked under
  "\<apache-superset-version>-dimagi-<index>" formatted Git tags.
  "apache-superset-version" is the upstream verion (e.g. "1.4.1"),
  and the index is an incremental number that keeps track of separate
  patched versions that we release from a given upstream version. For
  example, "1.4.1-dimagi-1" would mean the first patched release based
  on 1.4.1 and "1.4.1-dimagi-2" would mean a patched release made on
  top of "1.4.1-dimagi-1".

- Whenever a new patch is to be applied against our own release of the
  same upstream version, a new Git release is created with the index
  incremented (e.g. "1.4.1-dimagi-2")

- Whenever a new upstream release is available, all the patch commits
  from our last release are rebased onto the new upstream release,
  and a new Git release tag is created in the above format with the new
  upstream release version (e.g. "1.5.1-dimagi-1")

- Dimagi also maintains additional Portuguese translations for Superset.
  These cannot be rebased onto the upstream release. They need to be
  managed using tools for translations, and applied on top of the patch
  commits. For example, if "1.5.1" is the new upstream release version,
  then "1.5.1-dimagi-1" would be the tag for the rebased patch commits.
  Dimagi's Portuguese translations would be applied to that, and the
  result would be tagged "1.5.1-dimagi-2".

Based on these, the sections below give examples of adding our own
customization, applying Portuguese translations, and upgrading to a
newer Superset version.


#### Example of adding a new customization

Here is how to add a new customization to an existing Dimagi Superset
release.

1. Print all the tags containing "dimagi".
   ```bash
   $ git tag -l "*dimagi*"
   1.3.1-dimagi-1
   1.3.1-dimagi-2
   1.4.1-dimagi-1
   ```
   Pick the latest one, "1.4.1-dimagi-1".

2. If a branch at that tag doesn't already exist, then check out a new
   branch (e.g. "my_custom") at that tagged commit.
   ```bash
   $ git checkout -b my_custom 1.4.1-dimagi-1
   ```

3. Add new commits containing the new customizations, and open a pull
   request with the tag "1.4.1-dimagi-1" as its base.

4. Once merged, create a new tag with the index incremented, and push it
   to GitHub.
   ```bash
   $ git tag 1.4.1-dimagi-2
   $ git push origin 1.4.1-dimagi-2
   ```

Now a PyPI package can be built for "1.4.1-dimagi-2". See
[instructions to do that](#building-dimagi-superset-pypi-package) later
in this document.


#### Example of applying translations

Managing translations requires two tools:

- **msgmerge**, which is probably already be installed. It is included
  in the **gettext** package, which is one of the pre-install
  requirements for CommCare HQ dev environments on Linux.

- **po2json**, which needs to be installed using **npm**.

You will also need Dimagi's Portuguese translations. You can reach out
to members of the Solutions Division who work on projects in Mozambique
for an updated version. The current version should be named
`dimagi_pt_messages.po`, available in the last commit in the
`dimagi_pt` branch of
[Dimagi Superset] (https://github.com/dimagi/superset).

If you get a new version of Dimagi's Portuguese translations,
please _replace_ the last `dimagi_pt_messages.po` file, and commit it
in the `dimagi_pt` branch.

To generate updated language files:

0. (Optional) Set up a virtual Node environment (like a Python virtual
   environment) so that globally-installed Node packages aren't actually
   global.

   1. Enable your Python virtual environment.
      ```bash
      $ . venv/bin/activate
      ```

   2. Install **nodeenv**.
      ```bash
      $ pip install nodeenv
      ```

   3. Create a Node virtual environment and activate it.
      ```bash
      $ nodeenv install nenv
      $ . nenv/bin/activate
      ```

1. Install po2json.
   ```bash
   $ npm install -g po2json
   ```

2. Fetch the Apache Superset Portuguese translation files that you want
   to update. For example, if these translations will be released as
   Dimagi Superset 3.1.0, then you will want to merge the new Dimagi
   translations with the existing Apache Superset 3.1.0 translations.
   So you should check out the tag for the Apache Superset 3.1.0
   release. Use `msgmerge` to merge the new Dimagi translations with
   the existing file.
   ```bash
   $ git checkout 3.1.0
   $ msmerge superset/translations/pt/LC_MESSAGES/messages.po \
     /path/to/new/dimagi_pt_messages.po > /tmp/merged_pt_messages.po
   ```

3. Then switch back to the branch you're working in, and replace the
   current translations.
   ```bash
   $ git checkout my_custom
   $ mv /tmp/merged_pt_messages.po \
     superset/translations/pt/LC_MESSAGES/messages.po
   ```

4. Generate the messages.json files for all of the languages.

   (The **po2json** script only works in BASH. If you don't use BASH by
   default, you will need to switch to it, and activate your virtual
   environments. Again, this is only necessary if you are not already in
   a BASH shell.)
   ```bash
   $ bash
   $ . venv/bin/activate
   $ . nenv/bin/activate
   ```

   Run the **po2json** script to generate messages.json files for all of
   the languages.
   ```bash
   $ ./scripts/po2json
   ```

5. Commit the Portuguese files, and discard the rest. (BE CAREFUL!)
   ```bash
   $ git add superset/translations/pt/LC_MESSAGES/{messages.po,messages.json}
   $ git commit -m 'Updated PT language files'

   $ git reset --hard  # CAREFUL! DISCARDS ALL OTHER CHANGES!
   ```

6. Tag the commit as "{RELEASE}-dimagi-{VERSION}", and push the tag.
   ```bash
   $ git tag 3.1.0-dimagi-2
   $ git push origin 3.1.0-dimagi-2
   ```


#### Example of upgrading to a new upstream version

Let us assume that the last Dimagi Superset release was 2.1.3 and we
want to create a new release based on the new Apache Superset version
3.0.3. To create a new Dimagi Superset release, we need to know three
tags:

1. The previous Dimagi release *that doesn't include translations*:
   ```bash
   $ git tag -l '*dimagi*'
   1.4.1-dimagi-1
   2.0.0-dimagi-1
   2.0.1-dimagi-1
   2.1.3-dimagi-1  # <- This one
   2.1.3-dimagi-2  # <- Not this (hypothetical) one with translations

   $ export PREV_DIMAGI=2.1.3-dimagi-1
   ```

2. Its corresponding Apache release:
   ```bash
   $ export PREV_APACHE=2.1.3
   ```

3. The new Apache release that we want to create a Dimagi release for.
   Apache will have created a tag with the same name:
   ```bash
   $ export NEW_APACHE=3.0.3
   ```

Now that we have these three tag names, we will rebase our old
Dimagi-only commits onto the new Apache release tag, and create a new
branch. In this example, our new is named "3.0.3-dimagi". (See
[Git Rebasing](https://git-scm.com/book/en/v2/Git-Branching-Rebasing)
documentation for more about `git rebase --onto`.)

```bash
    $ git rebase --onto $NEW_APACHE $PREV_APACHE $PREV_DIMAGI
    $ git checkout -b 3.0.3-dimagi
    $ git push --set-upstream origin 3.0.3-dimagi
```

Tag the commit as "{RELEASE}-dimagi-{VERSION}", and push the tag.
```bash
    $ git tag 3.0.3-dimagi-1
    $ git push origin 3.0.3-dimagi-1
```

Now a "3.0.3-dimagi-1" PyPI package can be built using the section below.


### Building dimagi-superset PyPI package.

The Superset repo has a setup.py but it can not be directly pip
installed as there is superset-frontend that needs to be built and
shipped with the Python package. The exact set of instructions live at
https://github.com/apache/superset/tree/master/RELEASING#publishing-a-convenience-release-to-pypi.
At the point of writing this document, below are the instructions on
how to build a PyPI package from this. You may need to make sure that
the build instructions have remained the same before proceeding.

- git checkout to the latest created tag from one of the above steps.
- Create a virtualenv and activate it.
- Install base requirements and twine which are needed to build the
  package.
  ```
  pip install -r requirements/base.txt
  pip install twine
  ```
- Build the superset-frontend assets
  ```
  cd superset-frontend/
  npm ci && npm run build
  ```
- Build translations
  ```
  cd ../
  flask fab babel-compile --target superset/translations
  ```
- Build the python package
  ```
  python setup.py sdist
  ```

  This will create a tar file under `dist` directory with the version
  and name containing the Git release tag that you are on.

- Upload the tar using twine
  ```
  twine upload dist/apache-superset-${latest-dimagi-version}.tar.gz
  ```
  You can refer to 1Password for the PyPI credentials.

You should now be able to use this package inside
https://github.com/dimagi/hq_superset by referring to the release tag.
