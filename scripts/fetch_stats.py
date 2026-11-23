#!/usr/bin/env python3
"""Pobiera statystyki graczy z serwera (Craftserve) przez FTP, FTPS albo SFTP.

Pobiera TYLKO:
  <SERVER_DIR>/<WORLD_NAME>/stats/*.json  (statystyki graczy)
  <SERVER_DIR>/usercache.json             (nicki graczy)
Nic innego z serwera nie jest czytane ani publikowane.

Ustawienia (zmienne środowiskowe, w GitHubie jako Secrets / Variables):
  FTP_HOST, FTP_USER, FTP_PASSWORD   wymagane
  FTP_PORT       domyślnie 21 (ftp/ftps) albo 22 (sftp)
  FTP_PROTOCOL   ftp | ftps | sftp   (domyślnie sftp, Craftserve ma tylko SFTP)
  SERVER_DIR     folder serwera na FTP (domyślnie /)
  WORLD_NAME     nazwa folderu świata (domyślnie wykrywana sama)

Skrypt celowo nie wypisuje adresu serwera ani loginu, bo logi GitHub Actions są publiczne.
"""
import io
import json
import os
import posixpath
import sys
from datetime import datetime, timezone

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "raw")


def env(name, default=None, required=False):
    val = os.environ.get(name, "").strip()
    if not val:
        if required:
            sys.exit(f"Brak ustawienia {name}. Dodaj je w Settings → Secrets and variables → Actions.")
        return default
    return val


def save(rel, data):
    path = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


class FtpClient:
    def __init__(self, host, port, user, password, tls):
        import ftplib
        self.ftp = ftplib.FTP_TLS() if tls else ftplib.FTP()
        self.ftp.connect(host, port, timeout=60)
        self.ftp.login(user, password)
        if tls:
            self.ftp.prot_p()
        self.ftp.set_pasv(True)

    def list_json(self, path):
        """Zwraca [(nazwa, czas_modyfikacji_lub_None)]."""
        out = []
        try:
            for name, facts in self.ftp.mlsd(path, facts=["type", "modify"]):
                if facts.get("type") == "file" and name.endswith(".json"):
                    out.append((name, parse_mdtm(facts.get("modify"))))
            return out
        except Exception:
            pass  # serwer bez MLSD
        for full in self.ftp.nlst(path):
            name = posixpath.basename(full)
            if name.endswith(".json"):
                mtime = None
                try:
                    resp = self.ftp.sendcmd("MDTM " + posixpath.join(path, name))
                    mtime = parse_mdtm(resp.split()[-1])
                except Exception:
                    pass
                out.append((name, mtime))
        return out

    def list_dirs(self, path):
        try:
            return [n for n, f in self.ftp.mlsd(path, facts=["type"]) if f.get("type") == "dir"]
        except Exception:
            return [posixpath.basename(n) for n in self.ftp.nlst(path)]

    def read(self, path):
        buf = io.BytesIO()
        self.ftp.retrbinary("RETR " + path, buf.write)
        return buf.getvalue()

    def close(self):
        try:
            self.ftp.quit()
        except Exception:
            pass


class SftpClient:
    def __init__(self, host, port, user, password):
        import paramiko
        self.t = paramiko.Transport((host, port))
        self.t.connect(username=user, password=password)
        self.sftp = paramiko.SFTPClient.from_transport(self.t)

    def list_json(self, path):
        return [
            (a.filename, datetime.fromtimestamp(a.st_mtime, timezone.utc) if a.st_mtime else None)
            for a in self.sftp.listdir_attr(path)
            if a.filename.endswith(".json")
        ]

    def list_dirs(self, path):
        import stat
        return [a.filename for a in self.sftp.listdir_attr(path) if stat.S_ISDIR(a.st_mode or 0)]

    def read(self, path):
        with self.sftp.open(path, "rb") as f:
            return f.read()

    def close(self):
        self.sftp.close()
        self.t.close()


def detect_world(client, server_dir):
    """Szuka folderu świata: level-name z server.properties, potem 'world', potem dowolny folder z podfolderem stats."""
    candidates = []
    try:
        props = client.read(posixpath.join(server_dir, "server.properties")).decode("utf-8", "replace")
        for line in props.splitlines():  # czytamy tylko level-name, reszta pliku jest od razu odrzucana
            if line.startswith("level-name="):
                candidates.append(line.split("=", 1)[1].strip())
        del props
    except Exception:
        pass
    candidates.append("world")
    try:
        dirs = client.list_dirs(server_dir)
    except Exception:
        dirs = []
    candidates += [d for d in dirs if d not in candidates]
    for c in candidates:
        try:
            if "stats" in client.list_dirs(posixpath.join(server_dir, c)):
                print(f"Folder świata: {c}")
                return c
        except Exception:
            continue
    sys.exit("Nie znalazłem folderu świata ze statystykami. Foldery na serwerze: "
             + (", ".join(sorted(dirs)) or "(brak)") + ". Ustaw SERVER_DIR albo WORLD_NAME.")


def parse_mdtm(s):
    if not s:
        return None
    try:
        return datetime.strptime(s[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def main():
    proto = env("FTP_PROTOCOL", "sftp").lower()
    host = env("FTP_HOST", required=True)
    user = env("FTP_USER", required=True)
    password = env("FTP_PASSWORD", required=True)
    # dopuszczamy wklejenie adresu w formie sftp://host:port albo user@host
    host = host.split("://", 1)[-1].split("@")[-1].strip("/")
    port_env = env("FTP_PORT")
    if ":" in host:
        host, _, hp = host.partition(":")
        port_env = port_env or hp
    port = int(port_env or ("22" if proto == "sftp" else "21"))
    server_dir = env("SERVER_DIR", "/")
    world = env("WORLD_NAME")

    if proto == "sftp":
        try:
            client = SftpClient(host, port, user, password)
        except Exception as e:
            sys.exit(f"Nie mogę połączyć się przez SFTP ({type(e).__name__}: {e}). "
                     "Sprawdź FTP_PORT, FTP_USER i FTP_PASSWORD z zakładki Pliki w panelu Craftserve.")
    elif proto in ("ftp", "ftps"):
        client = FtpClient(host, port, user, password, tls=(proto == "ftps"))
    else:
        sys.exit("FTP_PROTOCOL musi być: ftp, ftps albo sftp")
    print(f"Połączono ({proto}).")

    try:
        if not world:
            world = detect_world(client, server_dir)
        stats_dir = posixpath.join(server_dir, world, "stats")
        try:
            files = client.list_json(stats_dir)
        except Exception as e:
            sys.exit(f"Nie mogę otworzyć folderu {world}/stats ({type(e).__name__}). Sprawdź SERVER_DIR i WORLD_NAME.")
        if not files:
            sys.exit(f"Folder {world}/stats jest pusty albo to zły folder. Sprawdź SERVER_DIR i WORLD_NAME.")
        mtimes = {}
        for name, mtime in files:
            save(posixpath.join("stats", name), client.read(posixpath.join(stats_dir, name)))
            mtimes[name[:-5]] = mtime.isoformat() if mtime else None
        save("mtimes.json", json.dumps(mtimes).encode())
        print(f"Pobrano statystyki {len(files)} graczy.")

        try:
            save("usercache.json", client.read(posixpath.join(server_dir, "usercache.json")))
            print("Pobrano usercache.json (nicki).")
        except Exception:
            print("Uwaga: brak usercache.json, zamiast nicków będą UUID.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
