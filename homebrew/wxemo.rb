class Wxemo < Formula
  desc "Export WeChat macOS emoticon stickers to local files"
  homepage "https://github.com/cv-yushen/wxemo_mac"
  url "https://github.com/cv-yushen/wxemo_mac/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "1076a520fe1a97b65ff4c47220c6d32e9a0517950490b6deaf2d342dd1444e22"
  license "MIT"
  version "0.1.0"

  depends_on "python@3.12"
  depends_on "openssl@3"

  def install
    libexec.install Dir["*"]

    (bin/"wxemo").write <<~EOS
      #!/bin/bash
      set -euo pipefail
      export WXEMO_PKG_ROOT="#{libexec}"
      export WXEMO_HOME="${WXEMO_HOME:-${HOME}/.wxemo}"
      mkdir -p "$WXEMO_HOME"
      exec "#{Formula["python@3.12"].opt_bin}/python3" "#{libexec}/cli.py" "$@"
    EOS
    chmod 0755, bin/"wxemo"
  end

  def caveats
    <<~EOS
      Private repo: set a GitHub token before install/upgrade:
        export HOMEBREW_GITHUB_API_TOKEN="$(gh auth token)"

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
