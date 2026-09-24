{ ttsDir ? ../../nix/nix/tts-read, scenario ? "before" }:
let
  pkgs = import ../../nix/nix { };
  ttsRead = import ttsDir pkgs;
  page = title: body: pkgs.writeText "page.html" ''
    <!doctype html><html><head><meta charset="utf-8"><title>${title}</title></head>
    <body style="font-size:28px"><p>${body}</p></body></html>
  '';
  site = pkgs.runCommand "site" { } ''
    cp -r ${./site} $out
    chmod -R u+w $out
    mkdir -p $out/b $out/c
    cp ${page "B" "Second selection. The quick brown fox jumps over the lazy dog."} $out/b/index.html
    cp ${page "C" "Third selection. Pack my box with five dozen liquor jugs."} $out/c/index.html
  '';
  mediaKeys = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/";
in
pkgs.testers.runNixOSTest {
  name = "tts-read-desktop-repro";
  nodes.machine = { lib, ... }: {
    virtualisation = {
      memorySize = 6144;
      cores = 8;
      resolution = { x = 1280; y = 800; };
      qemu.options = [
        "-audiodev wav,id=snd0,path=tts-audio.wav"
        "-device intel-hda"
        "-device hda-output,audiodev=snd0"
      ];
    };
    services.xserver.enable = true;
    services.displayManager.gdm.enable = true;
    services.desktopManager.gnome.enable = true;
    services.gnome.gnome-initial-setup.enable = false;
    services.displayManager.autoLogin = { enable = true; user = "a"; };
    users.users.a = { isNormalUser = true; uid = 1000; password = "a"; };
    services.pulseaudio.enable = false;
    security.rtkit.enable = true;
    services.pipewire = { enable = true; alsa.enable = true; pulse.enable = true; };
    environment.systemPackages = [ pkgs.google-chrome pkgs.firefox pkgs.strace pkgs.pipewire pkgs.dbus ttsRead ];
    services.nginx = {
      enable = true;
      virtualHosts.localhost.root = site;
    };

    systemd.user.services.tts-read = {
      description = "Read selection aloud";
      partOf = [ "graphical-session.target" ];
      after = [ "graphical-session.target" ];
      wantedBy = [ "graphical-session.target" ];
      serviceConfig = {
        ExecStart = "${ttsRead}/bin/tts-read --gapplication-service";
        Restart = "on-failure";
        Environment = [ "GST_DEBUG=appsrc:5" "GST_DEBUG_FILE=/tmp/tts-gst.log" "GST_DEBUG_NO_COLOR=1" ];
      };
    };
    programs.dconf.profiles.user.databases = [{
      settings = {
        "org/gnome/settings-daemon/plugins/media-keys".custom-keybindings = [ mediaKeys ];
        "org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0" = {
          name = "Read selection aloud";
          command = "${ttsRead}/bin/tts-read";
          binding = "<Super>r";
        };
        "org/gnome/shell".welcome-dialog-last-shown-version = "999";
        "org/gnome/desktop/session".idle-delay = lib.gvariant.mkUint32 0;
        "org/gnome/desktop/screensaver".lock-enabled = false;
      };
    }];
    systemd.user.units."org.gnome.Shell@wayland.service" = {
      overrideStrategy = "asDropin";
      text = ''
        [Service]
        Environment=MUTTER_DEBUG=focus,startup
      '';
    };
  };


  testScript = ''
    import glob, os, shutil, time, traceback

    out = os.environ["out"]
    t0 = time.monotonic()

    def mark(label):
        with open(f"{out}/marks.txt", "a") as log:
            log.write(f"{time.monotonic() - t0:9.3f} {label}\n")

    def usr(unit, cmd):
        machine.succeed(f"systemd-run --user --machine=a@.host --unit={unit} --collect {cmd}")

    def tts_pid():
        return machine.succeed("systemctl --user --machine=a@.host show -p MainPID --value tts-read").strip()

    def strace_on(name):
        pid = tts_pid()
        machine.succeed(f"systemd-run --unit={name} ${pkgs.strace}/bin/strace -f -tt -s 4000000 -xx -e trace=read,readv,recvmsg,recvfrom -o /tmp/{name}.log -p {pid}")
        machine.sleep(3)
        mark(f"{name} attached pid {pid}")

    def strace_off(name):
        machine.execute(f"systemctl stop {name}")
        mark(f"{name} detached")

    def shot(name):
        mark(f"shot {name}")
        machine.screenshot(name)

    CHROME = "${pkgs.google-chrome}/bin/google-chrome-stable --no-first-run --no-default-browser-check --password-store=basic http://localhost/tokens-too-cheap-to-meter/"

    def browse(unit, cmd, tag):
        usr(unit, cmd)
        machine.sleep(45)
        shot(f"{tag}-01-article")
        machine.send_key("ctrl-a")
        machine.sleep(2)
        shot(f"{tag}-02-selected")
        strace_on(f"strace-{tag}-1")
        mark(f"{tag} super-r 1: article selected, tts window closed")
        machine.send_key("meta_l-r")
        machine.sleep(10)
        strace_off(f"strace-{tag}-1")
        shot(f"{tag}-03-after-super-r-1")

    try:
        machine.wait_for_unit("display-manager.service")
        machine.wait_for_file("/run/user/1000/wayland-0")
        machine.wait_for_unit("default.target", "a")
        machine.wait_until_succeeds("systemctl --user --machine=a@.host is-active tts-read.service", timeout=300)
        pid = tts_pid()
        machine.execute(f"tr '\\0' '\\n' < /proc/{pid}/environ > /tmp/tts-env-at-start.txt")
        machine.execute("systemctl --user --machine=a@.host show-environment > /tmp/user-env-at-tts-start.txt")
        machine.sleep(20)
        machine.send_key("esc")
        mark("session up")
        machine.execute("systemctl --user --machine=a@.host show-environment > /tmp/user-env-later.txt")
        usr("rec", "${pkgs.pipewire}/bin/pw-record -P '{ stream.capture.sink=true }' /tmp/rec.wav")
        mark("recording")
        usr("dbusmon", "${pkgs.dbus}/bin/dbus-monitor --session \"type='method_call',interface='org.gtk.Application'\"")

        if "${scenario}" == "before":
            browse("chrome", CHROME, "chrome")
            for i in range(12):
                machine.sleep(20)
                shot(f"chrome-04-play-{i:02d}")

            mark("alt-tab to chrome")
            machine.send_key("alt-tab")
            machine.sleep(3)
            shot("chrome-05-focused")
            machine.send_key("ctrl-l")
            machine.sleep(1)
            machine.send_chars("localhost/b/\n")
            machine.sleep(6)
            machine.send_key("ctrl-a")
            machine.sleep(2)
            shot("chrome-06-page-b-selected")
            strace_on("strace-chrome-2")
            mark("chrome super-r 2: page B selected, tts window open")
            machine.send_key("meta_l-r")
            machine.sleep(15)
            strace_off("strace-chrome-2")
            shot("chrome-07-after-super-r-2")

            strace_on("strace-chrome-3")
            mark("alt-tab to the tts window")
            machine.send_key("alt-tab")
            machine.sleep(6)
            shot("chrome-08-tts-window-focused")
            mark("esc closes the tts window")
            machine.send_key("esc")
            machine.sleep(3)
            shot("chrome-09-closed")
            mark("chrome super-r 3: tts window closed")
            machine.send_key("meta_l-r")
            machine.sleep(12)
            strace_off("strace-chrome-3")
            shot("chrome-10-after-super-r-3")
            machine.send_key("esc")
            machine.sleep(2)
            machine.execute("systemctl --user --machine=a@.host stop chrome.service")
            machine.sleep(3)

            browse("firefox", "${pkgs.firefox}/bin/firefox http://localhost/tokens-too-cheap-to-meter/", "firefox")
            for i in range(6):
                machine.sleep(20)
                shot(f"firefox-04-play-{i:02d}")
        else:
            browse("chrome", CHROME, "chrome")
            for i in range(18 if "${scenario}" == "after" else 3):
                machine.sleep(20)
                shot(f"chrome-04-play-{i:02d}")
            for tag in ["b", "c"]:
                mark(f"alt-tab to chrome for page {tag}")
                machine.send_key("alt-tab")
                machine.sleep(3)
                machine.send_key("ctrl-l")
                machine.sleep(1)
                machine.send_chars(f"localhost/{tag}/\n")
                machine.sleep(6)
                machine.send_key("ctrl-a")
                machine.sleep(2)
                shot(f"chrome-05-page-{tag}-selected")
                strace_on(f"strace-open-{tag}")
                mark(f"super-r with the tts window open, page {tag} selected")
                machine.send_key("meta_l-r")
                machine.sleep(2)
                shot(f"chrome-06-page-{tag}-2s-after-super-r")
                machine.sleep(10)
                strace_off(f"strace-open-{tag}")
                shot(f"chrome-07-page-{tag}-after-super-r")
                if tag == "b":
                    strace_on("strace-focused")
                    mark("super-r with the tts window focused")
                    machine.send_key("meta_l-r")
                    machine.sleep(2)
                    shot("chrome-08-reader-focused-2s-after-super-r")
                    machine.sleep(10)
                    strace_off("strace-focused")
                    shot("chrome-09-reader-focused-after-super-r")
    except Exception:
        with open(f"{out}/scenario-error.txt", "w") as err:
            err.write(traceback.format_exc())
    finally:
        mark("collecting")
        machine.execute("systemctl --user --machine=a@.host stop rec.service dbusmon.service")
        machine.execute("journalctl -o short-monotonic --no-pager > /tmp/journal.txt")
        machine.execute("journalctl -o cat --no-pager _SYSTEMD_USER_UNIT=dbusmon.service > /tmp/dbusmon.txt")
        machine.execute("cp /tmp/tts-gst.log /tmp/tts-gst-copy.log")
        names = machine.succeed("ls /tmp/*.log /tmp/*.txt /tmp/*.wav 2>/dev/null || true").split()
        for path in names:
            try:
                machine.copy_from_vm(path, "vm")
            except Exception:
                pass
        machine.shutdown()
        for w in glob.glob(f"{machine.state_dir}/tts-audio.wav"):
            shutil.copy(w, out)
        mark("done")
  '';
}
