# ==========================================================
# ArchitectOS ComfyUI HTTP Runtime v3.2
# Real Result Tracking Layer
# Reduced Logging + Heavy Render Support
#
# FIX:
# - Real execution status tracking
# - Detect ComfyUI execution errors
# - Robust history parsing
# - Stable image extraction
# - Preserve long render support
# ==========================================================


import os
import time
import requests


from config import runtime_config as RC


# ==========================================================
# RENDER WAIT TIMEOUT
#
# The wait-for-render-completion budget used to be a bare `3600` default. A real
# render that was still sampling exceeded it and was cancelled while the GPU was
# healthy, so a legitimate job was lost to a client-side limit rather than to any
# engine fault. 3 hours covers long denoise / high-step renders on this hardware.
#
# SCOPE — this constant governs ONLY the render-completion wait. Deliberately
# left unchanged: the HTTP connect/read timeouts (60 s at the prompt POST, 10 s
# at the status calls) and the cancel-confirmation budget
# (ARCHITECTOS_COMFY_CANCEL_CONFIRM_TIMEOUT, 30 s), which are unrelated limits.
# ==========================================================
COMFY_RENDER_WAIT_TIMEOUT_SECONDS = 10800



class ComfyHTTPRuntime:


    VERSION = "3.2"



    def __init__(
        self,
        endpoint=None
    ):

        if endpoint is None:

            endpoint = RC.COMFYUI_URL

        self.endpoint = endpoint.rstrip("/")


        # Localhost render calls must NOT be routed through an ambient
        # HTTP_PROXY. On this machine HTTP_PROXY is set, and a proxied
        # POST to 127.0.0.1:8188 fails instead of reaching ComfyUI.
        self.session = requests.Session()

        self.session.trust_env = False


        print(
            "🚀 COMFYUI HTTP RUNTIME v3.2 ONLINE"
        )



    # ======================================================
    # SUBMIT WORKFLOW
    # ======================================================


    def submit(
        self,
        workflow,
        client_id=None
    ):


        url = (
            self.endpoint
            + "/prompt"
        )


        # ==================================================
        # FACADE-04D.3C-5B.1 — RACE B: OWN THE SUBMISSION WINDOW
        #
        # H1 releases ComfyUI's cached models after observing an EMPTY queue.
        # `GET /queue` and `POST /free` are not atomic, so a submission that
        # lands in between would have its models freed underneath it. Every
        # ArchitectOS submission therefore takes the same cross-process
        # ComfyUI lease H1 holds, which makes that window atomic for all
        # ArchitectOS-controlled renders.
        #
        # Only the POST itself is inside the lease: ComfyUI's own queueing of
        # concurrent renders is unchanged. If the lease cannot be taken in
        # time, NOTHING is submitted — the render fails truthfully instead of
        # bypassing the coordination.
        # ==================================================

        from core.runtime.gpu_handoff_v1 import comfyui_lease

        lease = comfyui_lease()

        if not lease.acquire():

            print(
                "⛔ COMFY SUBMIT BLOCKED: comfyui lease not available"
            )

            return {

                "status":
                    "error",

                "http_status":
                    None,

                "message":
                    "comfyui_lease_unavailable",

                "prompt_id":
                    None,

                "time":
                    time.time()

            }

        try:
            return self._submit_locked(workflow, url, client_id)

        finally:

            lease.release()


    def _submit_locked(
        self,
        workflow,
        url,
        client_id=None
    ):

        try:

            # ==================================================
            # REMOVE INTERNAL ARCHITECTOS METADATA
            # BEFORE COMFYUI EXECUTION
            # ==================================================

            workflow.pop(
                "_architectos_runtime",
                None
            )


            print(
                "🔥 COMFY WORKFLOW KEYS:",
                workflow.keys()
            )



            # ==================================================
            # REAL_SAMPLING_PROGRESS_B_PLUS — client_id in payload
            #
            # ComfyUI's POST /prompt accepts {"prompt": workflow,
            # "client_id": "<id>"}. The client_id is stored on the
            # server instance and used to route WebSocket progress
            # events back to the matching listener. Without it, no
            # progress events are emitted for this submission.
            # ==================================================

            payload = {"prompt": workflow}

            if client_id:
                payload["client_id"] = str(client_id)


            response = self.session.post(
                url,
                json=payload,
                timeout=10800
            )



            print(
                "🔥 COMFY RESPONSE:",
                response.status_code
            )


            try:

                data = response.json()

            except Exception:

                data = None



            prompt_id = (

                data.get("prompt_id")

                if isinstance(data, dict)

                else None

            )



            # ==================================================
            # TRUTHFUL SUBMIT STATUS
            #
            # A non-2xx response, an explicit ComfyUI error payload,
            # or a missing prompt_id is NEVER a successful submit.
            # ==================================================

            if response.status_code >= 400:


                return {

                    "status":
                        "error",


                    "http_status":
                        response.status_code,


                    "message":
                        "comfy_http_"
                        + str(response.status_code),


                    "prompt_id":
                        None,


                    "response":
                        data,


                    "time":
                        time.time()

                }



            if isinstance(data, dict) and data.get("error"):


                return {

                    "status":
                        "rejected",


                    "http_status":
                        response.status_code,


                    "message":
                        str(data.get("error")),


                    "prompt_id":
                        None,


                    "response":
                        data,


                    "time":
                        time.time()

                }



            return {

                "status":
                    "submitted",


                "http_status":
                    response.status_code,


                "prompt_id":
                    prompt_id,


                "response":
                    data,


                "time":
                    time.time()

            }



        except Exception as e:


            return {

                "status":
                    "error",


                "message":
                    str(e),


                "prompt_id":
                    None,


                "time":
                    time.time()

            }




    # ======================================================
    # HISTORY
    # ======================================================


    def history(
        self,
        prompt_id
    ):


        url = (
            self.endpoint
            + "/history/"
            + str(prompt_id)
        )


        try:


            response = self.session.get(
                url,
                timeout=10
            )


            return response.json()



        except Exception as e:


            return {

                "status":
                    "error",


                "message":
                    str(e)

            }




    # ======================================================
    # V4.3F — PROMPT-SPECIFIC CANCELLATION AND CONFIRMATION
    #
    # The installed ComfyUI (0.29.0, e578a8d7) exposes:
    #   GET  /queue                     -> {queue_running, queue_pending}
    #   POST /api/jobs/{id}/cancel      -> {"cancelled": bool}
    #
    # The /api/jobs/{id}/cancel route is the ONLY safe targeted cancel in this
    # build: a running job goes through PromptQueue.interrupt_if_running(),
    # which signals the interrupt under the queue mutex and only when that
    # exact prompt is still the running one. /interrupt with a prompt_id does
    # an equivalent check WITHOUT that mutex (a TOCTOU window), and /interrupt
    # with no body is a GLOBAL interrupt. Neither is used here.
    #
    # Nothing in this block can cancel another prompt: there is no queue wipe,
    # no global interrupt, and no id other than the one ArchitectOS submitted.
    # ======================================================

    def queue_state(self, timeout=None):
        """Read the live queue and extract prompt ids.

        Returns ``{"ok", "running", "pending", "reason"}``. ``ok`` is False for
        an unreachable, non-200 or malformed endpoint. An unreadable queue is
        NEVER reported as an empty one — that distinction is the whole point.
        """

        url = self.endpoint + "/queue"

        try:

            response = self.session.get(
                url,
                timeout=timeout if timeout is not None else 10
            )

            code = getattr(response, "status_code", None)

            if code != 200:

                return {
                    "ok": False, "running": [], "pending": [],
                    "reason": "queue_http_%s" % code,
                }

            data = response.json()

        except Exception as exc:

            return {
                "ok": False, "running": [], "pending": [],
                "reason": "queue_unreachable:%s" % exc,
            }

        if not isinstance(data, dict):

            return {
                "ok": False, "running": [], "pending": [],
                "reason": "queue_malformed",
            }

        running = data.get("queue_running")
        pending = data.get("queue_pending")

        if not isinstance(running, list) or not isinstance(pending, list):

            return {
                "ok": False, "running": [], "pending": [],
                "reason": "queue_malformed",
            }

        def _prompt_ids(items):

            ids = []

            for item in items:

                # ComfyUI queue items are tuples whose [1] is the prompt id.
                if isinstance(item, (list, tuple)) and len(item) > 1:

                    ids.append(str(item[1]))

                elif isinstance(item, str):

                    ids.append(item)

            return ids

        return {
            "ok": True,
            "running": _prompt_ids(running),
            "pending": _prompt_ids(pending),
            "reason": None,
        }

    def cancel_prompt(self, prompt_id, timeout=None):
        """Cancel exactly one prompt id. Never global, never a queue wipe."""

        if not prompt_id:

            return {"ok": False, "cancelled": False, "reason": "no_prompt_id"}

        url = (
            self.endpoint
            + "/api/jobs/"
            + str(prompt_id)
            + "/cancel"
        )

        try:

            response = self.session.post(
                url,
                timeout=timeout if timeout is not None else 10
            )

            code = getattr(response, "status_code", None)

            if code != 200:

                return {
                    "ok": False, "cancelled": False,
                    "reason": "cancel_http_%s" % code,
                }

            data = response.json()

        except Exception as exc:

            return {
                "ok": False, "cancelled": False,
                "reason": "cancel_unreachable:%s" % exc,
            }

        if not isinstance(data, dict):

            return {
                "ok": False, "cancelled": False,
                "reason": "cancel_malformed",
            }

        return {
            "ok": True,
            "cancelled": bool(data.get("cancelled")),
            "reason": None,
        }

    def confirm_inactive(self, prompt_id, timeout=None, interval=None):
        """Bounded poll until `prompt_id` is in neither queue list.

        An accepted cancel is NOT completion. Only the queue ceasing to list
        the prompt counts as confirmation, and an unreadable or malformed
        response never counts as confirmation.
        """

        budget = float(
            timeout if timeout is not None
            else os.environ.get(
                "ARCHITECTOS_COMFY_CANCEL_CONFIRM_TIMEOUT", 30
            )
        )

        step = float(
            interval if interval is not None
            else os.environ.get(
                "ARCHITECTOS_COMFY_CANCEL_CONFIRM_INTERVAL", 0.5
            )
        )

        started = time.time()
        polls = 0
        last_reason = None

        while True:

            polls += 1

            state = self.queue_state()

            if state.get("ok"):

                if (
                    str(prompt_id) not in state["running"]
                    and str(prompt_id) not in state["pending"]
                ):

                    return {
                        "confirmed": True,
                        "reason": "not_in_queue",
                        "polls": polls,
                        "elapsed_s": round(time.time() - started, 3),
                    }

            else:

                last_reason = state.get("reason")

            if (time.time() - started) >= budget:

                return {
                    "confirmed": False,
                    "reason": last_reason or "still_active",
                    "polls": polls,
                    "elapsed_s": round(time.time() - started, 3),
                }

            time.sleep(step)

    def _resolve_timeout_lifecycle(self, prompt_id):
        """Decide what a timeout actually means for the GPU.

        ``timeout``            — positively absent from the queue: the job is
                                 not executing, so releasing is safe.
        ``timeout_cancelled``  — cancel accepted AND the queue stopped listing
                                 it: safe.
        ``timeout_unconfirmed``— anything else, including an unreadable queue,
                                 a still-running job or an unconfirmed cancel.
                                 NOT safe; the caller must retain the lease.
        """

        state = self.queue_state()

        if not state.get("ok"):

            return {
                "status": "timeout_unconfirmed",
                "reason": "queue_unreadable",
                "queue": state,
                "cancel": None,
                "confirm": None,
            }

        active = (
            str(prompt_id) in state["running"]
            or str(prompt_id) in state["pending"]
        )

        if not active:

            return {
                "status": "timeout",
                "reason": "job_not_in_queue",
                "queue": state,
                "cancel": None,
                "confirm": {
                    "confirmed": True, "reason": "not_in_queue", "polls": 1,
                },
            }

        cancel = self.cancel_prompt(prompt_id)

        confirm = self.confirm_inactive(prompt_id)

        # An HTTP 200 is only "cancel accepted". The status reports what
        # actually happened: `cancelled: false` means the job was already
        # terminal when the cancel arrived, so nothing was cancelled even
        # though the queue is now clear.
        cancelled_actually = bool(
            cancel.get("ok") and cancel.get("cancelled")
        )

        if confirm.get("confirmed"):

            return {
                "status": (
                    "timeout_cancelled" if cancelled_actually else "timeout"
                ),
                "reason": (
                    "cancel_confirmed" if cancelled_actually
                    else "ended_before_cancel"
                ),
                "queue": state,
                "cancel": cancel,
                "confirm": confirm,
            }

        return {
            "status": "timeout_unconfirmed",
            "reason": "cancel_unconfirmed",
            "queue": state,
            "cancel": cancel,
            "confirm": confirm,
        }


    # ======================================================
    # WAIT RESULT
    # ======================================================


    def wait_for_result(
        self,
        prompt_id,
        timeout=COMFY_RENDER_WAIT_TIMEOUT_SECONDS,
        interval=15
    ):


        start = time.time()


        print(
            "⏳ COMFY RENDER STARTED:",
            prompt_id
        )


        last_status_log = 0



        while (
            time.time() - start
        ) < timeout:



            result = self.history(
                prompt_id
            )



            elapsed = int(
                time.time() - start
            )



            # ----------------------------------------------
            # STATUS LOG
            # ----------------------------------------------

            if elapsed - last_status_log >= 120:


                print(
                    f"⏳ COMFY PROCESSING | {elapsed}s | {prompt_id}"
                )


                last_status_log = elapsed




            # ----------------------------------------------
            # ERROR DETECTION
            # ----------------------------------------------


            error = self.detect_error(
                result
            )


            if error:


                print(
                    "❌ COMFY EXECUTION ERROR:",
                    error
                )


                return {

                    "status":
                        "execution_error",


                    "prompt_id":
                        prompt_id,


                    "error":
                        error,


                    "history":
                        result

                }




            # ----------------------------------------------
            # IMAGE RESULT
            # ----------------------------------------------


            images = self.extract_images(
                result
            )



            if images:


                print(
                    "✅ COMFY RESULT READY:",
                    len(images),
                    "image(s)"
                )


                return {

                    "status":
                        "completed",


                    "prompt_id":
                        prompt_id,


                    "images":
                        images,


                    "history":
                        result

                }

            videos = self.extract_videos(result)
            if videos:
                print("✅ COMFY VIDEO RESULT READY:", len(videos), "video(s)")
                return {
                    "status": "completed",
                    "prompt_id": prompt_id,
                    "videos": videos,
                    "history": result,
                }



            time.sleep(
                interval
            )






        print(
            "❌ COMFY TIMEOUT:",
            prompt_id
        )


        # ==================================================
        # V4.3F — A TIMEOUT IS NOT EVIDENCE THAT THE GPU IS IDLE
        #
        # The poll loop above gave up; ComfyUI may still be sampling. Resolve
        # the real lifecycle before anyone is allowed to release the render
        # lease: query the queue, cancel THIS prompt if it is still there, and
        # require the queue to stop listing it before reporting a terminal
        # state. Anything unresolved is reported as `timeout_unconfirmed`,
        # which the render runtime treats as "keep the lease".
        # ==================================================

        lifecycle = self._resolve_timeout_lifecycle(
            prompt_id
        )

        print(
            "🧯 COMFY TIMEOUT LIFECYCLE:",
            lifecycle.get("status"),
            "|",
            lifecycle.get("reason")
        )


        return {


            "status":
                lifecycle.get("status", "timeout_unconfirmed"),


            "prompt_id":
                prompt_id,


            "reason":
                lifecycle.get("reason"),


            "lifecycle":
                lifecycle

        }




    # ======================================================
    # ERROR DETECTION
    # ======================================================


    def detect_error(
        self,
        history
    ):


        if not isinstance(
            history,
            dict
        ):

            return None



        records = []



        if "status" in history:

            records.append(
                history
            )


        else:

            records.extend(
                history.values()
            )



        for item in records:


            if not isinstance(
                item,
                dict
            ):

                continue



            status = item.get(
                "status",
                {}
            )



            if isinstance(
                status,
                dict
            ):


                messages = status.get(
                    "messages",
                    []
                )


                for message in messages:


                    if (
                        isinstance(
                            message,
                            list
                        )
                        and len(message) > 0
                    ):


                        if message[0] in [

                            "execution_error",

                            "execution_failed"

                        ]:


                            return message



        return None




    # ======================================================
    # EXTRACT IMAGES
    # ======================================================


    def extract_images(
        self,
        history
    ):


        images = []



        if not isinstance(
            history,
            dict
        ):

            return images




        records = []



        # direct history record

        if "outputs" in history:


            records.append(
                history
            )



        else:


            records.extend(
                history.values()
            )




        for item in records:


            if not isinstance(
                item,
                dict
            ):

                continue




            outputs = item.get(
                "outputs",
                {}
            )



            if not isinstance(
                outputs,
                dict
            ):

                continue




            for node in outputs.values():


                if not isinstance(
                    node,
                    dict
                ):

                    continue




                for image in node.get(
                    "images",
                    []
                ):


                    images.append({

                        "filename":
                            image.get(
                                "filename"
                            ),


                        "subfolder":
                            image.get(
                                "subfolder",
                                ""
                            ),


                        "type":
                            image.get(
                                "type",
                                "output"
                            )

                    })



        return images


    def extract_videos(self, history):
        """Extract files emitted by SaveVideo and legacy video-combine nodes."""
        videos = []
        if not isinstance(history, dict):
            return videos
        records = [history] if "outputs" in history else list(history.values())
        for item in records:
            if not isinstance(item, dict):
                continue
            outputs = item.get("outputs", {})
            if not isinstance(outputs, dict):
                continue
            for node in outputs.values():
                if not isinstance(node, dict):
                    continue
                for key in ("videos", "gifs"):
                    for video in node.get(key, []):
                        if isinstance(video, dict) and video.get("filename"):
                            videos.append({
                                "filename": video.get("filename"),
                                "subfolder": video.get("subfolder", ""),
                                "type": video.get("type", "output"),
                                "format": video.get("format", "mp4"),
                            })
        return videos
