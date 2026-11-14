# Test Report — Universal AI Video Production Studio

**Test Command:** `PYTHONPATH=. .venv/bin/pytest tests/test_studio_e2e.py -v`  
**Result:** **8 passed in 113.10s (0:01:53)**  
**Desktop Build:** `cd desktop && npx tsc --noEmit && npm run build` — **Passed** (`dist/assets/index-De26QBvo.js`, 1.16s)

## Executed Test Cases

| Test | Scope | Outcome | Verified Artifacts & Behavior |
| :--- | :--- | :--- | :--- |
| `test_integration_openmontage_and_registry` | OpenMontage 164-tool & 13-pipeline discovery, hardware/engine registry | **PASSED** | `openmontage_tools_count >= 160`, `13` pipelines, `ffmpeg` available |
| `test_integration_openwhispr_and_voice_parser` | OpenWhispr adapter & Voice-to-Action parser | **PASSED** | Confirmation gate on `regenerate_scene`, multilingual subtitle parsing (`hi`, `en`) |
| `test_e2e_1_animated_cartoon_with_dialogue_music_sfx` | 2D animated cartoon (`hyperframes`), TTS, music, SFX, FFprobe QA | **PASSED** | `stems/music.wav`, `stems/sfx.wav`, `qa_reports[0].passed == 1` |
| `test_e2e_2_faceless_educational_short_word_captions` | 9:16 vertical Short (`1080x1920`), word-level captions, QA | **PASSED** | `subtitles/subtitles_en.srt`, `status == "completed"` |
| `test_e2e_3_and_4_documentary_and_educational_chapters` | 5-min documentary render + 15-min (`900.0s`) 4-chapter, 12-scene plan | **PASSED** | Documentary QA passed; 15-min course planned into 4 chapters / 12 scenes |
| `test_e2e_5_resumable_and_single_scene_regeneration_preserves_edits` | Manual timeline edit preservation, single-scene regeneration, pause & resume | **PASSED** | Scene 2 `manual_edited=1` & `zoom=1.25` preserved after Scene 1 regeneration; pause/resume completed |
| `test_e2e_6_3d_animated_scene_non_remotion_path` | Non-Remotion 3D rendering path (`threejs` 3D projection) | **PASSED** | `renders/*.threejs.html` + 3D MP4 rendered & passed FFprobe QA |
| `test_e2e_7_and_8_voice_editing_and_multilingual_export` | Multilingual (`en`, `hi`) subtitles, voice confirmation gate, MP4 export | **PASSED** | `subtitles_en.srt`, `subtitles_hi.srt`, voice confirmation flow, `1280x720` MP4 export |
