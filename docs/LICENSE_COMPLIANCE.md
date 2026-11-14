# License & Attribution Compliance

## 1. Upstream Licenses

- **OpenMontage (`integrations/OpenMontage`):** Licensed under **GNU Affero General Public License v3.0 (AGPL-3.0)**.
  - *Obligation:* Because the Studio backend imports and invokes OpenMontage's tool registry and pipeline loader, any distribution of the combined backend or network-accessible deployment of the Studio backend must comply with **AGPL-3.0** source-availability requirements.
  - All original `LICENSE` and `THIRD_PARTY_NOTICES.md` files in `integrations/OpenMontage` are preserved intact.
- **OpenWhispr (`integrations/openwhispr`):** Licensed under the **MIT License**.
  - *Obligation:* Preserve copyright and MIT permission notices (`integrations/openwhispr/LICENSE`). Optional downloaded speech models (e.g., `orukeet-v0.1.0`) carry **CC-BY-SA-4.0**.

## 2. Third-Party Media & Engine Notices

- **FFmpeg:** Homebrew build with `--enable-gpl --enable-version3` (GPLv3).
- **Remotion (`integrations/OpenMontage/remotion-composer`):** Subject to Remotion's commercial license terms for organizations exceeding free-tier thresholds.
- **Ink Theater Assets:** `patrickhand.ttf`, `PlayfairDisplay`, `SpaceGrotesk` (SIL OFL 1.1); CMU Mocap clips (attribution required).
- **Asset Provenance:** Every generated or retrieved audio/video asset in `studio.db` (`assets.license`) records its actual source and license rather than falsely claiming copyright-free status.
