#!/bin/bash
# Maintainer release helper: tag → GitHub Release → update Homebrew tap sha256
#
# Usage:
#   bash scripts/release.sh 0.1.2
set -euo pipefail
cd "$(dirname "$0")/.."

VER="${1:?usage: release.sh <version without v, e.g. 0.1.2>}"
TAG="v${VER}"
OWNER="$(gh api user -q .login)"
REPO="wxemo_mac"
TAP_REPO="homebrew-wxemo"

echo "==> Ensuring clean working tree"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree not clean; commit or stash first." >&2
  exit 1
fi

echo "==> Push main"
git push origin main

echo "==> Tag $TAG"
if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Tag $TAG already exists locally"
else
  git tag -a "$TAG" -m "wxemo $TAG"
fi
git push origin "$TAG"

echo "==> GitHub Release"
if gh release view "$TAG" >/dev/null 2>&1; then
  echo "Release $TAG already exists"
else
  gh release create "$TAG" --title "wxemo $TAG" --generate-notes --latest
fi

echo "==> Compute sha256 for GitHub archive tarball"
TMP="$(mktemp)"
curl -fsSL -H "Authorization: Bearer $(gh auth token)" -L \
  "https://github.com/${OWNER}/${REPO}/archive/refs/tags/${TAG}.tar.gz" \
  -o "$TMP"
SHA="$(shasum -a 256 "$TMP" | awk '{print $1}')"
rm -f "$TMP"
echo "sha256=$SHA"

echo "==> Update local Formula template"
# NOTE: wrapper resolves python3 at runtime (do not hardcode python@3.12 path).
cat > homebrew/wxemo.rb <<RUBY
class Wxemo < Formula
  desc "Export WeChat macOS emoticon stickers to local files"
  homepage "https://github.com/${OWNER}/${REPO}"
  url "https://github.com/${OWNER}/${REPO}/archive/refs/tags/${TAG}.tar.gz"
  sha256 "${SHA}"
  license "MIT"
  version "${VER}"

  depends_on "python3"
  depends_on "openssl@3"

  def install
    libexec.install Dir["*"]

    (bin/"wxemo").write <<~EOS
      #!/bin/bash
      set -euo pipefail
      export WXEMO_PKG_ROOT="#{libexec}"
      export WXEMO_HOME="\${WXEMO_HOME:-\${HOME}/.wxemo}"
      mkdir -p "\$WXEMO_HOME"
      PY=""
      for c in "#{Formula["python3"].opt_bin}/python3" python3 python3.13 python3.12 python3.11; do
        if [[ "\$c" == /* ]]; then
          [[ -x "\$c" ]] && PY="\$c" && break
        elif command -v "\$c" >/dev/null 2>&1; then
          PY="\$(command -v "\$c")"
          break
        fi
      done
      if [[ -z "\$PY" ]]; then
        echo "wxemo: python3 not found. Try: brew install python3" >&2
        exit 1
      fi
      exec "\$PY" "#{libexec}/cli.py" "\$@"
    EOS
    chmod 0755, bin/"wxemo"
  end

  def caveats
    <<~EOS
      User data (keys & exports):
        ~/.wxemo/

      Requires Xcode Command Line Tools (lldb):
        xcode-select --install

      Quick start:
        wxemo status
        wxemo wizard
    EOS
  end

  test do
    assert_match "wizard", shell_output("#{bin}/wxemo --help")
  end
end
RUBY

echo "==> Update tap repo Formula"
TAP_DIR="$(mktemp -d)"
gh auth setup-git >/dev/null
git clone "https://github.com/${OWNER}/${TAP_REPO}.git" "$TAP_DIR"
mkdir -p "$TAP_DIR/Formula"
cp homebrew/wxemo.rb "$TAP_DIR/Formula/wxemo.rb"
(
  cd "$TAP_DIR"
  git add Formula/wxemo.rb
  if git diff --cached --quiet; then
    echo "Tap formula unchanged"
  else
    git commit -m "wxemo ${TAG}"
    git push origin HEAD
  fi
)
rm -rf "$TAP_DIR"

echo "==> Done"
echo "Users install with:"
echo "  brew tap ${OWNER}/wxemo && brew trust ${OWNER}/wxemo && brew install wxemo"
