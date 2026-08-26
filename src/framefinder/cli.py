from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

from .downloader import AcquisitionError, acquire_video
from .models import SearchResult
from .ocr import RapidOCREngine
from .search import DialogueFrameFinder, build_search_result, save_frame
from .speech import FasterWhisperEngine, TranscriptionError
from .video import VideoReadError, VideoReader, format_timestamp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="find-dialogue-frame",
        description=(
            "Find the first video frame containing a requested on-screen dialogue."
        ),
    )
    parser.add_argument("source", help="Local video path or public HTTP(S) video URL")
    parser.add_argument("dialogue", help="Exact dialogue text to locate")
    parser.add_argument(
        "--mode",
        choices=("auto", "speech", "ocr"),
        default="auto",
        help="Use speech timestamps, visible-text OCR, or speech then OCR (default: auto)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Artifact directory (default: ./output)",
    )
    parser.add_argument(
        "--format",
        default=(
            "best[ext=mp4][acodec!=none][vcodec!=none]/"
            "best[acodec!=none][vcodec!=none]/"
            "bestvideo[height<=720]+bestaudio/bestvideo+bestaudio/best"
        ),
        help="yt-dlp format selector used for URL inputs",
    )
    parser.add_argument(
        "--no-check-certificates",
        action="store_true",
        help="Disable TLS certificate verification for yt-dlp (use only when required)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=80.0,
        help="Combined recognition/fuzzy threshold from 0-100 (default: 80)",
    )
    parser.add_argument(
        "--asr-model",
        default="base.en",
        help="faster-whisper model name or local model path (default: base.en)",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="ASR language code, or 'auto' for detection (default: en)",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="ASR device such as cpu or cuda (default: cpu)",
    )
    parser.add_argument(
        "--compute-type",
        default="int8",
        help="faster-whisper compute type (default: int8)",
    )
    parser.add_argument(
        "--coarse-interval",
        type=float,
        default=2.0,
        help="Seconds between initial OCR samples (default: 2.0)",
    )
    parser.add_argument(
        "--fallback-interval",
        type=float,
        default=0.5,
        help="Seconds between fallback samples; 0 disables fallback (default: 0.5)",
    )
    parser.add_argument(
        "--stable-frames",
        type=int,
        default=2,
        help="Consecutive matches required during exact refinement (default: 2)",
    )
    parser.add_argument(
        "--region",
        choices=("full", "bottom", "top"),
        default="full",
        help="Frame region sent to OCR (default: full)",
    )
    parser.add_argument(
        "--max-ocr-width",
        type=int,
        default=1280,
        help="Downscale wider OCR images for speed (default: 1280)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress messages; final result is still printed",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    def progress(stage: str, done: int, total: int, score: float) -> None:
        if args.quiet:
            return
        if stage == "fine" or done == 1 or done % 100 == 0 or done == total:
            print(
                f"[{stage}] {done}/{total} frames; current score={score:.1f}",
                file=sys.stderr,
            )

    try:
        video_path = acquire_video(
            args.source,
            output_dir / "downloads",
            format_selector=args.format,
            no_check_certificates=args.no_check_certificates,
        )
        if not args.quiet:
            print(f"Video: {video_path}", file=sys.stderr)

        result: SearchResult | None = None
        result_frame = None
        speech_candidate: tuple[SearchResult, np.ndarray | None] | None = None

        if args.mode in {"auto", "speech"}:
            if not args.quiet:
                print(
                    f"Loading speech model '{args.asr_model}' and transcribing...",
                    file=sys.stderr,
                )
            speech_result, speech_frame = _run_speech(
                video_path=video_path,
                source=args.source,
                dialogue=args.dialogue,
                threshold=args.threshold,
                model_name=args.asr_model,
                language=None if args.language == "auto" else args.language,
                device=args.device,
                compute_type=args.compute_type,
                model_cache=output_dir / "models",
            )
            speech_candidate = (speech_result, speech_frame)
            if speech_result.status == "found" or args.mode == "speech":
                result, result_frame = speech_result, speech_frame

        if result is None and args.mode in {"auto", "ocr"}:
            if not args.quiet:
                print("Loading offline OCR models and scanning frames...", file=sys.stderr)
            finder = DialogueFrameFinder(
                RapidOCREngine(),
                threshold=args.threshold,
                coarse_interval_seconds=args.coarse_interval,
                fallback_interval_seconds=args.fallback_interval,
                stable_frames=args.stable_frames,
                region=args.region,
                max_ocr_width=args.max_ocr_width,
                progress=progress,
            )
            located, metadata, diagnostics = finder.locate(video_path, args.dialogue)
            ocr_result = build_search_result(
                located=located,
                metadata=metadata,
                dialogue=args.dialogue,
                source=args.source,
                image_path=None,
                diagnostics={"mode": "ocr", **diagnostics},
            )
            result, result_frame = ocr_result, located.frame if located else None

            if (
                ocr_result.status != "found"
                and speech_candidate is not None
                and speech_candidate[0].confidence > ocr_result.confidence
            ):
                result, result_frame = speech_candidate

        if result is None:  # defensive; argparse constrains mode values
            raise RuntimeError("No search mode was selected.")

        image_path = None
        if result_frame is not None:
            image_path = output_dir / (
                "exact-frame.png" if result.status == "found" else "candidate-frame.png"
            )
            save_frame(image_path, result_frame)
            result.output_image = str(image_path)

        result_path = output_dir / "result.json"
        result_path.write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except (
        AcquisitionError,
        VideoReadError,
        TranscriptionError,
        RuntimeError,
        ValueError,
        OSError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Status    : {result.status}")
    if result.frame_number is not None:
        print(f"Timestamp : {result.timestamp}")
        print(f"Frame     : {result.frame_number} (0-based)")
        print(f'Text      : "{result.extracted_text}"')
        print(f"Confidence: {result.confidence:.1f}/100")
        print(f"Image     : {result.output_image}")
    print(f"JSON      : {result_path}")
    return 0 if result.status == "found" else 2


def _run_speech(
    *,
    video_path: Path,
    source: str,
    dialogue: str,
    threshold: float,
    model_name: str,
    language: str | None,
    device: str,
    compute_type: str,
    model_cache: Path,
) -> tuple[SearchResult, np.ndarray | None]:
    model_cache.mkdir(parents=True, exist_ok=True)
    engine = FasterWhisperEngine(
        model_name=model_name,
        device=device,
        compute_type=compute_type,
        download_root=model_cache,
    )
    match, diagnostics = engine.find(
        video_path,
        dialogue,
        threshold=threshold,
        language=language,
    )
    with VideoReader(video_path) as reader:
        metadata = reader.metadata
        if match is None:
            return SearchResult(
                status="not_found",
                target_text=dialogue,
                source=source,
                video_path=str(video_path),
                recognition_method="speech",
                fps=metadata.fps,
                notes=["Speech recognition found no sufficiently similar phrase."],
                diagnostics=diagnostics,
            ), None

        frame_number = min(
            metadata.frame_count - 1,
            max(0, math.floor(match.start_seconds * metadata.fps + 1e-9)),
        )
        frame = reader.read(frame_number)

    status = "found" if match.exact else "uncertain"
    notes = [
        "The frame contains the ASR-estimated start of the first matched spoken word."
    ]
    if not match.exact:
        notes.append("The best speech match did not reach the configured threshold.")
    return SearchResult(
        status=status,
        target_text=dialogue,
        source=source,
        video_path=str(video_path),
        timestamp_seconds=match.start_seconds,
        timestamp=format_timestamp(match.start_seconds),
        frame_number=frame_number,
        extracted_text=match.text,
        recognition_method="speech",
        confidence=round(match.score, 3),
        fuzzy_score=round(match.fuzzy_score, 3),
        recognizer_confidence=round(match.asr_confidence, 5),
        fps=metadata.fps,
        notes=notes,
        diagnostics=diagnostics,
    ), frame


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
