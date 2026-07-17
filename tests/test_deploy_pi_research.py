from scripts.remote_perception_eval import deploy_command


def test_deploy_includes_safety_runtime_but_no_stock_or_models():
    command = deploy_command("rpicarbox-1", "/tmp/tiny_pi_car")
    joined = " ".join(command)
    assert "playground/autonomy/" in joined
    assert "playground/autoresearch/" in joined
    assert "playground/experiments/" in joined
    assert "MasterPi" not in joined
    assert "--exclude models" in joined
