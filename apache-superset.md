## Dimagi Superset Fork

This is a fork of https://github.com/apache/superset. This repo is a maintained to build a slightly customized version of the original [Superset PyPi package](https://pypi.org/project/apache-superset/). 


### Making changes

We build most of customization and integration inside https://github.com/dimagi/hq_superset and avoid
customizing this repo directly so that we don't diverge too much from original Superset. 
But we do that when it's very complicated to do it inside hq_superset and when it's super easy to do it 
in this fork.

In this spirit, 
- if the change is specific to CommCareHQ, try to implement the customization in https://github.com/dimagi/hq_superset itself. 
- if the change is not specific to CommCare HQ and is useful to outside users, try to create a Pull Request against the upstream repo https://github.com/apache/superset itself. 
- If that is too complicated, you may add a change to this repo. 

To include your changes in https://github.com/dimagi/hq_superset you will need to track it under proper git release tag, build a new Pypi release from your changes and reference that release in hq_superset requirements. Below sections explain how to do this.

### Keeping track of your changes via git tags

Please note that maintaining this repo in sync with the upstream changes, our own customizations and maintaining proper PyPi versions (also the git tags) is very difficult  (Google 'vendor branch pattern'). For this reason we don't aim to keep the master branch in sync with the upstream.

https://github.com/apache/superset repo maintains git tags to indicate the version of each released Superset PyPi package. For example, see 1.4.1 release [here](https://github.com/apache/superset/releases/tag/1.4.1). We follow simple conventions below to maintain a patched version of the package that we can use in https://github.com/dimagi/hq_superset.

- All our patches/customizations are done against an upstream release tag. We release only these patched versions of the upstream versions. 
- By convention, these releases are tracked under `<apache-superset-version>-dimagi-<index>` formatted git tags. `apache-superset-version` is the upstream verion (for e.g. 1.4.1), and the index is an incremental number that keeps track of separate patched versions that we release from a given upstream version. For example, `1.4.1-dimagi-1` would mean the first patched release based on 1.4.1 and `1.4.1-dimagi-2` would mean a patched release made on top of `1.4.1-dimagi-1`.
- Whenever a new upstream release is available, all the patch commits from our last release are cherry-picked onto the new upstream release and a new git release tag is created in the above format with the new upstream release version (for e.g. `1.5.1-dimagi-1`)
- Whenever a new patch is to be applied against our own release of the same upstream version, a new git release is created with the index incremented (for e.g. `1.4.1-dimagi-2`)

Based on these, below sections explain the examples of adding our own customization or upgrading to a newer superset version.

#### Example to add new customization

Here is how a new customization is done on existing release.
- Do `git tag -l "*dimagi*"` which will print all tags containing dimagi. Pick the latest tag (for e.g. `1.4.1-dimagi-1`)
- git checkout -b mybranch $latest-dimagi-tag
- Add new commits containing the new customizations and PR against $latest-dimagi-tag
- Once merged, create a new tag with the index incremented `git tag $new-tag` and push it to github.

If we take the example of `1.4.1-dimagi-1` for the latest released tag, the commands will be following
- git tag -l "*dimagi*"
  1.3.1-dimagi-1
  1.3.1-dimagi-2
  1.4.1-dimagi-1
- git checkout -b mybranch 1.4.1-dimagi-1
- Add commits and PR.
- git tag 1.4.1-dimagi-2
- git push origin 1.4.1-dimagi-2

Now, 1.4.1-dimagi-2 PyPi package can be built using the section below.

#### Example to update to a new upstream version

- Fetch latest tags from upstream superset repo (for e.g. 1.5.1 being the latest)
- List dimagi specific tags using `git tag -l "*dimagi*"`. Pick the latest tag (for e.g. 1.4.1-dimagi-1).
- git checkout -b mybranch $latest-upstream-tag.
- Find list of commits that are Dimagi specific by doing `git log <superset-tag>..<dimagi-tag>`
- Cherry-pick all the above commits onto mybranch
- Create a new release for the new version by 'git tag  <apache-superset-release-tag>-dimagi-<index>'

If we take the example of 1.4.1-dimagi-1 for the latest released tag, the commands will be following
- git fetch upstream (let's say the latest upstream is 1.5.1)
- git tag -l "*dimagi*"
  1.3.1-dimagi-1
  1.3.1-dimagi-2
  1.4.1-dimagi-1
  1.4.1-dimagi-2
- git checkout -b mybranch 1.4.1-dimagi-2
- git log 1.4.1..1.4.1-dimagi-2 (shows all the commits containing our patches)
- Do "git cherr-pick" for all of above commits.
- git tag 1.5.1-dimagi-1
- git push origin 1.5.1-dimagi-1

Now, 1.4.1-dimagi-2 PyPi package can be built using the section below.

### Building dimagi-superset Pypi package.

The Superset repo has a setup.py but it can not be directly pip installed as there is superset-frontend that needs to be built and shipped with the Python package. The exact set of instructions live at https://github.com/apache/superset/tree/master/RELEASING#publishing-a-convenience-release-to-pypi. At the point of writing this document, below are the instructions on how to build a Pypi package from this. You may need to make sure that the build instructions have remained the same before proceeding.

- git checkout to the latest created tag from one of the above steps.
- Create a virtualenv and activate it.
- Install base requirements and twine which are needed to build the package.
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
  This will create a tar file under `dist` directory with the version and name containing the git release tag that you are on.
- Upload the tar using twine
  ```
  twine upload dist/apache-superset-${latest-dimagi-version}.tar.gz
  ```
  You can refer to 1Password for the Pypi credentials.

You should now be able to use this package inside https://github.com/dimagi/hq_superset by referring to the release tag.