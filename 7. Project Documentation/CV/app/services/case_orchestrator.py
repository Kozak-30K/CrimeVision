"""Coordinate local AI analysis for all evidence in a case."""

from pathlib import Path

from app.services.anchor_event_scoring import identify_anchor_events
from app.services.audio_transcription import AudioTranscriptionService
from app.services.case_store import CaseStore
from app.services.cross_modal_fusion import fuse_observations
from app.services.evidence_integrity import verify_evidence_integrity
from app.services.forensic_schema import create_observation
from app.services.object_detection import ObjectDetectionService
from app.services.observation_adapter import (
    audio_result_to_observations,
    image_results_to_observations,
)
from app.services.scene_description import SceneDescriptionService
from app.services.temporal_sync import synchronize_observations
from app.services.video_analysis import VideoAnalysisService
from app.services.video_observation_adapter import (
    video_results_to_observations,
)


def analyze_case(store: CaseStore, case_id: str) -> dict:
    """Analyze registered evidence and save a consolidated case report."""

    case = store.get_case(case_id)
    if case is None:
        raise KeyError(f"Case not found: {case_id}")

    evidence_items = store.list_evidence(case_id)

    observations = []
    evidence_results = []
    failures = []

    # Initialize models only when their modality is encountered.
    detector = None
    captioner = None
    transcriber = None
    video_analyzer = None

    for evidence in evidence_items:
        evidence_id = evidence["evidence_id"]
        modality = evidence["modality"]
        storage_path = evidence.get("metadata", {}).get("storage_path")

        item_result = {
            "evidence_id": evidence_id,
            "filename": evidence["filename"],
            "modality": modality,
            "status": "pending",
        }

        try:
            if not storage_path:
                raise ValueError("Evidence has no registered storage path.")

            path = Path(storage_path).expanduser()

            integrity = verify_evidence_integrity(
                store,
                case_id,
                evidence_id,
                path,
                persist=True,
            )
            item_result["integrity"] = integrity

            if integrity["status"] != "verified_match":
                item_result["status"] = "integrity_failed"
                item_result["message"] = (
                    "Analysis skipped because the file did not match "
                    "the registered evidence digest and size."
                )
                evidence_results.append(item_result)
                continue

            if modality == "image":
                if detector is None:
                    detector = ObjectDetectionService()
                if captioner is None:
                    captioner = SceneDescriptionService()

                detection_result = detector.analyze_image(str(path))
                scene_result = captioner.describe_image(str(path))

                store.save_analysis(
                    case_id, "object_detection",
                    detection_result, evidence_id=evidence_id,
                )
                store.save_analysis(
                    case_id, "scene_description",
                    scene_result, evidence_id=evidence_id,
                )

                item_observations = image_results_to_observations(
                    evidence, detection_result, scene_result
                )

            elif modality == "audio":
                if transcriber is None:
                    transcriber = AudioTranscriptionService()

                transcription_result = transcriber.transcribe_audio(
                    str(path)
                )

                store.save_analysis(
                    case_id, "audio_transcription",
                    transcription_result, evidence_id=evidence_id,
                )

                item_observations = audio_result_to_observations(
                    evidence, transcription_result
                )

            elif modality == "video":
                if video_analyzer is None:
                    video_analyzer = VideoAnalysisService()

                video_result = video_analyzer.analyze_video(
                    video_path=path,
                    source_sha256=evidence["sha256"],
                )

                store.save_analysis(
                    case_id, "video_analysis",
                    video_result, evidence_id=evidence_id,
                )

                item_observations = video_results_to_observations(
                    evidence, video_result
                )

            else:
                raise ValueError(
                    f"Unsupported evidence modality: {modality}"
                )

            store.save_analysis(
                case_id,
                "normalized_observations",
                {"observations": item_observations},
                evidence_id=evidence_id,
            )

            observations.extend(item_observations)
            item_result["status"] = "completed"
            item_result["observation_count"] = len(item_observations)

        except Exception as exc:
            # Preserve registered evidence and continue with other items.
            item_result["status"] = "failed"
            item_result["error"] = str(exc)
            failures.append({
                "evidence_id": evidence_id,
                "modality": modality,
                "error": str(exc),
            })

            store.save_analysis(
                case_id,
                "evidence_analysis_failure",
                {
                    "evidence_id": evidence_id,
                    "modality": modality,
                    "error": str(exc),
                    "requires_human_review": True,
                },
                evidence_id=evidence_id,
            )

        evidence_results.append(item_result)

    # Combine observations without treating temporal proximity as proof.
    fusion_result = fuse_observations(observations)
    timeline_result = synchronize_observations(observations)
    anchor_result = identify_anchor_events(
        observations,
        associations=fusion_result.get("associations", []),
    )

    report = {
        "analysis_type": "case_forensic_report",
        "case_id": case_id,
        "case_title": case["title"],
        "status": (
            "completed_with_failures"
            if failures
            else "completed"
        ),
        "evidence_count": len(evidence_items),
        "completed_evidence_count": sum(
            item["status"] == "completed" for item in evidence_results
        ),
        "failed_evidence_count": len(failures),
        "evidence_results": evidence_results,
        "observations": observations,
        "timeline": timeline_result,
        "cross_modal_analysis": fusion_result,
        "anchor_event_candidates": anchor_result,
        "failures": failures,
        "limitations": [
            "AI-generated findings are preliminary and require human review.",
            "Temporal proximity or cross-modal association does not prove "
            "that observations share a cause or event.",
            "Review-priority scores are not probabilities of guilt.",
            "Hash matching verifies consistency with the registered digest, "
            "not authenticity before registration or full chain of custody.",
        ],
        "requires_human_review": True,
    }

    saved_report = store.save_analysis(
        case_id,
        "case_forensic_report",
        report,
        evidence_id=None,
    )
    report["result_id"] = saved_report["result_id"]

    return report
