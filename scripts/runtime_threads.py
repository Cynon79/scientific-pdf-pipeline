"""Version-scoped CPU policy for dependency thread pools; no package files edited."""
from importlib.metadata import version


def configure_threads(threads: int) -> dict:
    if version("mineru") != "2.0.4" or version("rapid-table") != "1.0.5":
        raise RuntimeError("Thread adapter requires the verified MinerU/RapidTable versions")
    import ultralytics.utils.torch_utils as yolo_torch
    from rapid_table.table_structure.utils import OrtInferSession

    # Ultralytics select_device() uses this module value to reset torch threads.
    yolo_torch.NUM_THREADS = threads
    original = OrtInferSession._init_sess_opts

    def session_options(config):
        options = original(config)
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        options.add_session_config_entry("session.inter_op.allow_spinning", "0")
        return options

    OrtInferSession._init_sess_opts = staticmethod(session_options)
    return {"torch_threads": threads, "onnx_intra_op_threads": 1,
            "onnx_inter_op_threads": 1, "onnx_spinning": False,
            "ultralytics_version": version("ultralytics"),
            "rapid_table_version": version("rapid-table")}
