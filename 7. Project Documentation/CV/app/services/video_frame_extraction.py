
from pathlib import Path
from typing import Any

import cv2


def extract_video_frames(
    video_path: str | Path,
    sample_interval_seconds: float = 1.0,
    max_frames: int = 3600,
) -> dict[str, Any]:
    """Extract timestamped video frames at a fixed interval."""

    video_path = Path(video_path)

    if not video_path.is_file():
        raise ValueError("Video file does not exist.")

    if sample_interval_seconds <= 0:
        raise ValueError("Sample interval must be greater than zero.")

    if max_frames < 1:
        raise ValueError("max_frames must be at least 1.")

    capture = cv2.VideoCapture(str(video_path))

    if not capture.isOpened():
        capture.release()
        raise ValueError("OpenCV could not open the video.")

    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

        if fps <= 0 or frame_count <= 0:
            raise ValueError("Video FPS or frame count is invalid.")

        duration_seconds = frame_count / fps

        output_dir = (
            video_path.parent
            / f"{video_path.stem}_frames"
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        frames = []
        sample_index = 0
        timestamp = 0.0

        while timestamp < duration_seconds:
            if len(frames) >= max_frames:
                # Respect the configured work cap; the returned metadata
                # still reports the full source duration and sampled count.
                break

            capture.set(
                cv2.CAP_PROP_POS_MSEC,
                timestamp * 1000.0,
            )

            success, frame = capture.read()

            if not success or frame is None:
                # A failed seek/read must not silently create a false
                # observation or assign the wrong timestamp.
                raise RuntimeError(
                    f"Could not read video frame at {timestamp:.3f} seconds."
                )

            frame_name = f"frame_{sample_index:06d}.jpg"
            frame_path = output_dir / frame_name

            if not cv2.imwrite(str(frame_path), frame):
                raise RuntimeError(
                    f"Could not save extracted frame {frame_name}."
                )

            frames.append({
                "frame_index": sample_index,
                "timestamp_seconds": round(timestamp, 3),
                "frame_file": frame_name,
                "frame_path": str(frame_path),
                "width": int(frame.shape[1]),
                "height": int(frame.shape[0]),
            })

            sample_index += 1
            timestamp = sample_index * sample_interval_seconds

        return {
            "source_video": video_path.name,
            "fps": fps,
            "original_frame_count": frame_count,
            "duration_seconds": duration_seconds,
            "sample_interval_seconds": sample_interval_seconds,
            "sampled_frame_count": len(frames),
            "frames": frames,
        }

    finally:
        capture.release()
