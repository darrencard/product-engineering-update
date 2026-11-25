#!/usr/bin/env bash
# Build a release's assets from its tag: a zip made by `git archive` and a SHA256SUMS file.
#
# Usage: tools/release.sh 0.5.0
#
# The tag v<version> must already exist on the merged commit on main, and pyproject.toml at that tag
# must say the same version. The assets go to dist/ (ignored by git). The script builds and checks;
# it publishes nothing. It prints the `gh release create` command to run once the person says ship.
set -euo pipefail

version="${1:?usage: tools/release.sh <version>, for example 0.5.0}"
tag="v${version}"
name="product-technology-leader-report-${version}"
root="$(git rev-parse --show-toplevel)"
cd "$root"

if ! git rev-parse -q --verify "refs/tags/${tag}" > /dev/null; then
  echo "release: there is no tag ${tag}. Merge the release to main, then tag that commit: git tag -a ${tag} -m \"${tag}\"" >&2
  exit 1
fi
declared="$(git show "${tag}:pyproject.toml" | sed -n 's/^version = "\(.*\)"$/\1/p')"
if [ "${declared}" != "${version}" ]; then
  echo "release: pyproject.toml at ${tag} says ${declared:-nothing}, not ${version}. Bump the version before tagging." >&2
  exit 1
fi

mkdir -p dist
rm -f "dist/${name}.zip" dist/SHA256SUMS
git archive --format=zip --prefix="${name}/" -o "dist/${name}.zip" "${tag}"
(cd dist && shasum -a 256 "${name}.zip" > SHA256SUMS && shasum -a 256 -c SHA256SUMS)

echo "release: built dist/${name}.zip and dist/SHA256SUMS from ${tag}."
echo "release: to publish, after the person says ship:"
echo "  gh release create ${tag} dist/${name}.zip dist/SHA256SUMS --title \"${tag}\" --notes-file <notes>"
echo "release: then pin ${tag} in the README prompt and on /update."
echo "release: then run the mini eval and commit the trend row: python3 evals/ablation/mini.py --version ${version} (about \$5)."
