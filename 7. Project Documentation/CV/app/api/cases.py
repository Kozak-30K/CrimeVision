
"""Case-management API for CrimeVision."""

from flask import Blueprint, current_app, jsonify, request


cases_bp = Blueprint("cases", __name__)


def get_case_store():
    """Return the shared application-level CaseStore."""
    return current_app.extensions["crimevision_case_store"]


@cases_bp.post("/cases")
def create_case():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    try:
        case = get_case_store().create_case(
            title=data.get("title"),
            description=data.get("description", ""),
        )
        return jsonify({"case": case}), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        current_app.logger.exception("Failed to create case")
        return jsonify({"error": "Case creation failed."}), 500


@cases_bp.get("/cases")
def list_cases():
    status = request.args.get("status")

    try:        
        store = get_case_store()
        cases = store.list_cases(status=status)
        counts = store.get_record_counts()

        return jsonify({
            "count": len(cases),
            "cases": cases,
            **counts,
        }), 200

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        current_app.logger.exception("Failed to list cases")
        return jsonify({"error": "Case listing failed."}), 500


@cases_bp.get("/cases/<case_id>")
def get_case(case_id):
    try:
        case = get_case_store().get_case(case_id)

        if case is None:
            return jsonify({"error": "Case not found."}), 404

        return jsonify({"case": case}), 200
    except Exception:
        current_app.logger.exception("Failed to retrieve case")
        return jsonify({"error": "Case retrieval failed."}), 500


@cases_bp.patch("/cases/<case_id>")
def update_case(case_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    allowed_fields = {"title", "description", "status"}
    unexpected_fields = set(data) - allowed_fields

    if unexpected_fields:
        return jsonify({
            "error": "Unsupported fields.",
            "fields": sorted(unexpected_fields),
        }), 400

    try:
        case = get_case_store().update_case(
            case_id,
            title=data.get("title"),
            description=data.get("description"),
            status=data.get("status"),
        )
        return jsonify({"case": case}), 200
    except KeyError:
        return jsonify({"error": "Case not found."}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        current_app.logger.exception("Failed to update case")
        return jsonify({"error": "Case update failed."}), 500


@cases_bp.get("/cases/<case_id>/evidence")
def list_case_evidence(case_id):
    try:
        evidence = get_case_store().list_evidence(case_id)
        return jsonify({
            "case_id": case_id,
            "count": len(evidence),
            "evidence": evidence,
        }), 200
    except KeyError:
        return jsonify({"error": "Case not found."}), 404
    except Exception:
        current_app.logger.exception("Failed to list case evidence")
        return jsonify({"error": "Evidence listing failed."}), 500


@cases_bp.get("/cases/<case_id>/analyses")
def list_case_analyses(case_id):
    try:
        analyses = get_case_store().list_analyses(case_id)
        return jsonify({
            "case_id": case_id,
            "count": len(analyses),
            "analyses": analyses,
        }), 200
    except KeyError:
        return jsonify({"error": "Case not found."}), 404
    except Exception:
        current_app.logger.exception("Failed to list case analyses")
        return jsonify({"error": "Analysis listing failed."}), 500


@cases_bp.post("/cases/<case_id>/analyses")
def save_case_analysis(case_id):
    """Save a completed analysis under a case."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    analysis_type = data.get("analysis_type")
    result = data.get("result")
    evidence_id = data.get("evidence_id")

    if not isinstance(analysis_type, str) or not analysis_type.strip():
        return jsonify({"error": "analysis_type must be a non-empty string."}), 400

    if not isinstance(result, dict):
        return jsonify({"error": "result must be a JSON object."}), 400

    if evidence_id is not None and not isinstance(evidence_id, str):
        return jsonify({"error": "evidence_id must be a string or null."}), 400

    try:
        analysis = get_case_store().save_analysis(
            case_id=case_id,
            analysis_type=analysis_type,
            result=result,
            evidence_id=evidence_id,
        )
        return jsonify({"analysis": analysis}), 201

    except KeyError:
        return jsonify({"error": "Case not found."}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except (TypeError, OverflowError):
        return jsonify({"error": "Analysis result contains unsupported JSON values."}), 400
    except Exception:
        current_app.logger.exception("Failed to save analysis for case %s", case_id)
        return jsonify({"error": "Analysis could not be saved."}), 500


@cases_bp.get("/analyses/<result_id>")
def get_saved_analysis(result_id):
    """Retrieve one saved analysis without rerunning the model."""
    try:
        analysis = get_case_store().get_analysis(result_id)

        if analysis is None:
            return jsonify({"error": "Analysis record not found."}), 404

        return jsonify({"analysis": analysis}), 200

    except Exception:
        current_app.logger.exception(
            "Failed to retrieve analysis record %s", result_id
        )
        return jsonify({"error": "Analysis retrieval failed."}), 500


@cases_bp.post("/cases/<case_id>/analyze")
def analyze_case(case_id):
    """Run the local multimodal pipeline for a case."""
    from app.services.case_orchestrator import analyze_case as run_analysis

    try:
        report = run_analysis(get_case_store(), case_id)
        return jsonify({"report": report}), 200

    except KeyError:
        return jsonify({"error": "Case not found."}), 404

    except Exception:
        current_app.logger.exception(
            "Case analysis failed for case %s", case_id
        )
        return jsonify({"error": "Case analysis failed. Check server logs."}), 500
