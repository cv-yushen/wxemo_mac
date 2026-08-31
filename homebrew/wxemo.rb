class Wxemo < Formula
  desc "Export WeChat macOS emoticon stickers to local files"
  homepage "https://github.com/cv-yushen/wxemo_mac"
  url "https://github.com/cv-yushen/wxemo_mac/archive/refs/tags/v0.1.2.tar.gz"
  sha256 "31fa6791476a54f98f7f4c23572aa6897e1f4def73bf401dc73017fb5f030be0"
  license "MIT"
  version "0.1.2"

  depends_on "python3"
  depends_on "openssl@3"

  def install
    libexec.install Dir["*"]

    (bin/"wxemo").write <<~EOS
      #!/bin/bash
      set -euo pipefail
      export WXEMO_PKG_ROOT="#{libexec}"
      export WXEMO_HOME="${WXEMO_HOME:-${HOME}/.wxemo}"
      mkdir -p "$WXEMO_HOME"
      PY=""
      for c in "#{Formula["python3"].opt_bin}/python3" python3 python3.13 python3.12 python3.11; do
        if [[ "$c" == /* ]]; then
          [[ -x "$c" ]] && PY="$c" && break
        elif command -v "$c" >/dev/null 2>&1; then
          PY="$(command -v "$c")"
          break
        fi
      done
      if [[ -z "$PY" ]]; then
        echo "wxemo: python3 not found. Try: brew install python3" >&2
        exit 1
      fi
      exec "$PY" "#{libexec}/cli.py" "$@"
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
