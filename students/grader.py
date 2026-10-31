import os
import json
import base64
import requests
import math
import time
import logging

logger = logging.getLogger(__name__)


class ResilientGrader:
    """
    Grades student screening tests using local memory for MCQs
    and Gemini Cloud APIs with strict rubrics for open-ended Vivas.
    Includes time-wise decay weighting on MCQ answers.

    Resilience Strategy (SIH-hardened):
    - 3-attempt exponential-backoff retry on Gemini
    - Automatic failover to Groq (llama-3.3-70b-versatile) if all Gemini attempts fail
    - Zero-Unearned-Score policy only triggers if ALL providers fail
    """

    @staticmethod
    def get_token_questions(session_token: str) -> list:
        """
        Decodes the base64 session token. 
        Note: This is deprecated now that we use secure, database-backed sessions!
        """
        try:
            clean_token = session_token.strip().replace("\n", "").replace("\r", "").strip('"').strip("'")
            padding_needed = len(clean_token) % 4
            if padding_needed:
                clean_token += '=' * (4 - padding_needed)
                
            decoded_bytes = base64.b64decode(clean_token.encode())
            decoded_text = decoded_bytes.decode('utf-8', errors='ignore')
            return json.loads(decoded_text, strict=False).get("questions", [])
        except Exception as e:
            raise ValueError(f"Invalid or corrupted session token. Details: {str(e)}")

    @staticmethod
    def evaluate_test_submission(submitted_answers: list, original_questions: list, resume_rating: float) -> dict:
        """
        Grades the test submission using questions retrieved directly from the database.
        - MCQs: Evaluated instantly in-memory with custom Time-Decay multipliers.
        - Vivas: Evaluated via Gemini API with structured feedback.
        """
        total_mcq_score = 0
        mcq_count = 0
        viva_score_sum = 0
        viva_count = 0
        viva_fault_detected = False
        
        detailed_feedback = []
        skill_gaps = []

        for q in original_questions:
            q_id = q["id"]
            q_category = q.get("category", "TECHNICAL")
            sub_ans = next((item for item in submitted_answers if item["id"] == q_id), None)
            student_answer_text = sub_ans["answer_text"].strip() if sub_ans else ""
            student_justification = sub_ans.get("justification", "").strip() if sub_ans else ""
            time_taken = sub_ans.get("time_taken_seconds", 15) if sub_ans else 15

            if q["type"] == "MCQ":
                mcq_count += 1
                correct_letter = (q.get("correct_answer") or "").strip()[:1].upper()
                
                # Robust option letter extraction from candidate's answer
                student_choice = student_answer_text.strip()
                student_letter = ""
                if student_choice:
                    if len(student_choice) >= 2 and student_choice[:2].upper() in ["A)", "B)", "C)", "D)"]:
                        student_letter = student_choice[:1].upper()
                    elif student_choice[:1].upper() in ["A", "B", "C", "D"] and (len(student_choice) == 1 or student_choice[1] in [".", ":", " ", ")"]):
                        student_letter = student_choice[:1].upper()
                    elif q.get("options"):
                        for opt_idx, opt in enumerate(q["options"]):
                            if student_choice.lower() in opt.lower() or opt.lower() in student_choice.lower():
                                student_letter = chr(65 + opt_idx)
                                break

                is_correct = bool(student_letter and correct_letter and student_letter == correct_letter)
                
                if is_correct:
                    if time_taken <= 15:
                        multiplier = 1.0
                    elif time_taken >= 60:
                        multiplier = 0.7
                    else:
                        multiplier = 1.0 - 0.3 * ((time_taken - 15) / 45)
                    score = int(100 * multiplier)
                    feedback_msg = f"Correct choice ({correct_letter}). Answered in {time_taken}s."
                    gap = None
                    if student_justification:
                        growth_tip = f"Sound rationale: '{student_justification}'. Reinforce this standard by integrating it into live edge-case scenarios."
                    else:
                        growth_tip = "Solid conceptual understanding. Continue articulating your underlying trade-off reasoning."
                else:
                    score = 0
                    feedback_msg = f"Selected {student_letter or 'unanswered'}; standard benchmark is {correct_letter}."
                    
                    # Constructive diagnosis of reasoning divergence using candidate's rationale
                    if q_category == "SOFT_SKILL":
                        gap = "Cross-Functional Collaboration & Stakeholder Alignment"
                        if student_justification:
                            growth_tip = f"Your rationale considered: '{student_justification}'. In professional practice, transparent alignment checkpoints and documented trade-offs prevent drift and protect stakeholder trust."
                        else:
                            growth_tip = "Focus on collaborative alignment, transparent trade-off communication, and documented consensus when managing conflicting priorities."
                    else:
                        gap = f"Domain Methodology & Verification Standards ({q.get('difficulty', 'Core')})"
                        if student_justification:
                            growth_tip = f"Your approach noted: '{student_justification}'. The established standard emphasizes metric-driven profiling and regulatory compliance before committing to implementation decisions."
                        else:
                            growth_tip = f"Review established verification benchmarks for {q.get('explanation', 'this concept')} to bridge this gap."

                    skill_gaps.append({
                        "skill": q.get("question_text", "Core Competency")[:60] + "...",
                        "category": q_category,
                        "identified_gap": gap,
                        "growth_recommendation": growth_tip
                    })

                total_mcq_score += score
                detailed_feedback.append({
                    "id": q_id,
                    "question_text": q["question_text"],
                    "type": "MCQ",
                    "category": q_category,
                    "student_answer": student_answer_text,
                    "justification": student_justification,
                    "score": score,
                    "feedback": f"{feedback_msg} {q['explanation']}",
                    "skill_gap": gap,
                    "growth_tip": growth_tip
                })

            elif q["type"] == "VIVA":
                viva_count += 1
                viva_score, evaluation_feedback = ResilientGrader._grade_viva_resilient(
                    question=q["question_text"],
                    student_answer=student_answer_text,
                    rubric=q["explanation"]
                )
                
                if viva_score is None:
                    viva_fault_detected = True
                    score = 0
                    v_gap = "Viva Evaluation Interruption"
                    v_tip = "Retest required for genuine verification."
                else:
                    score = viva_score
                    viva_score_sum += score
                    if score < 70:
                        v_gap = "Architectural Synthesis & Edge-Case Depth" if q_category == "TECHNICAL" else "Crisis Resolution & Risk Communication"
                        v_tip = f"Deepen practical discussion on failure modes and documented mitigation: {q['explanation']}"
                        skill_gaps.append({
                            "skill": q.get("question_text", "Reasoning & Viva")[:60] + "...",
                            "category": q_category,
                            "identified_gap": v_gap,
                            "growth_recommendation": v_tip
                        })
                    else:
                        v_gap = None
                        v_tip = "Strong analytical articulation. Continue refining high-stakes trade-off presentations."

                detailed_feedback.append({
                    "id": q_id,
                    "question_text": q["question_text"],
                    "type": "VIVA",
                    "category": q_category,
                    "student_answer": student_answer_text,
                    "justification": student_justification,
                    "score": score,
                    "feedback": evaluation_feedback,
                    "skill_gap": v_gap,
                    "growth_tip": v_tip
                })

        final_mcq_avg = total_mcq_score / mcq_count if mcq_count > 0 else 0

        # Strict Verification Guarantee: If external AI failed during viva grading,
        # NEVER award free or unearned scores. Acknowledge the fault on our side and mandate a retest.
        if viva_fault_detected:
            return {
                "success": False,
                "retest_required": True,
                "fault_acknowledged": True,
                "message": (
                    "Oops! Our automated viva evaluation engine encountered an unexpected interruption on our end while evaluating your response. "
                    "Because we uphold rigorous academic and industry verification standards, we never award arbitrary or unearned scores. "
                    "We have acknowledged this fault on our side, kept your session open, and prepared an immediate retest so you can obtain a genuine verified score. "
                    "Please submit again or retry when ready!"
                ),
                "cognitive_score": 0,
                "mcq_average": int(final_mcq_avg),
                "viva_average": 0,
                "confidence_score": 0,
                "feedback_log": detailed_feedback,
                "skill_gaps": skill_gaps
            }

        final_viva_avg = viva_score_sum / viva_count if viva_count > 0 else 0
        
        # Weighted Cognitive Score: 30% MCQ (with Time-Decay), 70% Viva (Reasoning-focused)
        cognitive_score = (0.3 * final_mcq_avg) + (0.7 * final_viva_avg)

        # Apply Capped Root Confidence Score (CS) Formula
        gap = max(0, resume_rating - cognitive_score)
        penalty_coefficient = 0.4
        penalty = penalty_coefficient * math.sqrt(gap / 100.0)
        confidence_score = int(cognitive_score * (1 - penalty))

        return {
            "success": True,
            "retest_required": False,
            "fault_acknowledged": False,
            "message": "Assessment evaluated successfully.",
            "cognitive_score": int(cognitive_score),
            "mcq_average": int(final_mcq_avg),
            "viva_average": int(final_viva_avg),
            "confidence_score": min(max(0, confidence_score), 100),
            "feedback_log": detailed_feedback,
            "skill_gaps": skill_gaps
        }

    @staticmethod
    def _grade_viva_resilient(question: str, student_answer: str, rubric: str) -> tuple:
        """
        Multi-provider resilient viva grading pipeline:
        1. Try Gemini with 3 exponential-backoff retries
        2. If all Gemini attempts fail, failover to Groq
        3. Only return None (triggering retest) if ALL providers fail
        """
        if not student_answer:
            return 0, "No answer submitted."

        # --- Attempt 1: Gemini with retries ---
        gemini_result = ResilientGrader._grade_viva_via_gemini(question, student_answer, rubric)
        if gemini_result[0] is not None:
            return gemini_result

        logger.warning(f"Gemini grading failed after retries. Attempting Groq failover...")

        # --- Attempt 2: Groq failover ---
        groq_result = ResilientGrader._grade_viva_via_groq(question, student_answer, rubric)
        if groq_result[0] is not None:
            return groq_result

        logger.error("ALL AI providers failed for viva grading. Triggering retest protocol.")
        return None, (
            "Oops! Our automated grading engine experienced a technical hiccup across all providers on our end. "
            "Because we maintain strict verification standards and never award arbitrary scores, this response requires a retest. "
            "We sincerely apologize for this inconvenience on our side!"
        )

    @staticmethod
    def _grade_viva_via_gemini(question: str, student_answer: str, rubric: str) -> tuple:
        """
        Task 3: Response Grading via Gemini with 3-attempt exponential backoff.
        Routed to gemini-3.1-flash-lite by default.
        """
        api_key = os.getenv("GEMINI_API_KEY")
        model = os.getenv("MODEL_GRADER", "gemini-3.1-flash-lite")
        
        if not api_key:
            return None, "Gemini API key not configured."

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        system_prompt = (
            "You are a strict and objective domain-expert examiner. Grade the candidate's answer to the "
            "viva question based on the provided expert grading rubric across their field of study or professional domain. "
            "You must score the answer strictly on a scale of 0 to 100.\n\n"
            "Use these explicit rubric anchors:\n"
            "- Score 90-100: Excellent answer. Mentions core concepts, specific methodologies/tools/metrics, and practical trade-offs.\n"
            "- Score 50-80: Acceptable answer. Understands the basic concepts but lacks specific operational or practical details.\n"
            "- Score 10-40: Weak answer. Vague, superficial mentions of keywords with no real domain comprehension.\n"
            "- Score 0: Irrelevant, empty, or plagiarized answer.\n\n"
            "You must return ONLY a structured JSON object matching this exact schema:\n"
            "{\n"
            "  \"score\": 85,\n"
            "  \"feedback\": \"Detailed, objective 2-sentence feedback explaining why this score was awarded.\"\n"
            "}"
        )

        user_content = (
            f"Question: {question}\n"
            f"Candidate Answer: {student_answer}\n"
            f"Grading Rubric Anchor: {rubric}"
        )

        response_schema = {
            "type": "OBJECT",
            "properties": {
                "score": {"type": "INTEGER"},
                "feedback": {"type": "STRING"}
            },
            "required": ["score", "feedback"]
        }

        payload = {
            "contents": [{
                "parts": [{"text": f"{system_prompt}\n\nCandidate Submission:\n{user_content}"}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": response_schema,
                "temperature": 0.1
            }
        }

        # 3-attempt exponential backoff: 2s, 4s, 8s
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=payload, timeout=120)
                response.raise_for_status()
                
                result_json = response.json()
                text_response = result_json["candidates"][0]["content"]["parts"][0]["text"]
                content = json.loads(text_response)
                
                return int(content["score"]), content["feedback"]
            except Exception as e:
                wait_time = 2 ** (attempt + 1)  # 2s, 4s, 8s
                logger.warning(
                    f"Gemini grading attempt {attempt + 1}/{max_retries} failed: {e}. "
                    f"{'Retrying in ' + str(wait_time) + 's...' if attempt < max_retries - 1 else 'All retries exhausted.'}"
                )
                if attempt < max_retries - 1:
                    time.sleep(wait_time)

        return None, "Gemini grading failed after 3 retry attempts."

    @staticmethod
    def _grade_viva_via_groq(question: str, student_answer: str, rubric: str) -> tuple:
        """
        Failover grading via Groq (llama-3.3-70b-versatile).
        Uses OpenAI-compatible chat completions API with JSON mode.
        """
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.warning("GROQ_API_KEY not set — Groq failover skipped.")
            return None, "Groq API key not configured."

        model = os.getenv("GROQ_GRADER_MODEL", "llama-3.3-70b-versatile")
        url = "https://api.groq.com/openai/v1/chat/completions"

        system_prompt = (
            "You are a strict and objective domain-expert examiner. Grade the candidate's answer to the "
            "viva question based on the provided expert grading rubric. "
            "Score strictly on a scale of 0 to 100.\n\n"
            "Rubric anchors:\n"
            "- 90-100: Excellent. Core concepts, specific methodologies, practical trade-offs.\n"
            "- 50-80: Acceptable. Basic understanding but lacks operational specifics.\n"
            "- 10-40: Weak. Vague keywords with no real domain comprehension.\n"
            "- 0: Irrelevant, empty, or plagiarized.\n\n"
            "Return ONLY JSON: {\"score\": <int>, \"feedback\": \"<2-sentence feedback>\"}"
        )

        user_content = (
            f"Question: {question}\n"
            f"Candidate Answer: {student_answer}\n"
            f"Grading Rubric Anchor: {rubric}"
        )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 256
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # 2-attempt retry on Groq (it's fast, so shorter backoff)
        for attempt in range(2):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=30)
                response.raise_for_status()

                result = response.json()
                content_text = result["choices"][0]["message"]["content"]
                content = json.loads(content_text)

                score = int(content.get("score", 0))
                feedback = content.get("feedback", "Graded via Groq failover.")
                logger.info(f"Groq failover grading successful: score={score}")
                return score, feedback
            except Exception as e:
                logger.warning(f"Groq grading attempt {attempt + 1}/2 failed: {e}")
                if attempt == 0:
                    time.sleep(1)

        return None, "Groq failover grading also failed."
