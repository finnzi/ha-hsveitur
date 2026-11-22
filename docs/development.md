# Development

## Dev Home Assistant (Docker)

    docker compose up -d          # http://localhost:8123, first run: create a user
    docker compose logs -f homeassistant
    docker compose restart homeassistant   # after changing integration code

Then Settings > Devices & services > Add integration > "HS Veitur" and enter the
keys from your local `.env`. Setup validation and the first import take minutes
(the HS Veitur API takes 40-200 s per call). Check the result under
Developer tools > Statistics (`hsveitur:energy_<meter>`) and the Energy dashboard.

Reset everything: `docker compose down && rm -rf dev/config/{.storage,*.db*,*.log*,.HA_VERSION}`.

## Tests

    docker compose run --rm tests   # Python 3.14 + pytest-homeassistant-custom-component

HA-free tests also run locally: `.venv/bin/pytest`.

## Releasing

HACS shows the latest GitHub release as the installed version (without one it shows a
commit hash). Releases are created by `.github/workflows/release.yml`:

1. Bump `version` in `custom_components/hsveitur/manifest.json` (and the version in the
   README status note) on a branch, PR it into `dev`, then merge `dev` into `main`.
2. Tag the merge commit on `main` and push the tag:
   `git tag v0.2.0 && git push origin v0.2.0`
3. The workflow fails if the tag doesn't match the manifest version; otherwise it creates
   the release with generated notes.
