from app.tools.tee.ta_generator import TAGenerator


def test_ta_generator_aes_gcm_template_includes_commands():
    gen = TAGenerator()
    result = gen._build_files(
        name="aes_demo",
        ta_uuid="12345678-1234-5678-1234-567812345678",
        template="aes_gcm_simple",
    )
    ta_c = result["aes_demo_ta.c"]
    ta_h = result["aes_demo_ta.h"]
    assert "TA_CMD_AES_GCM_ENCRYPT" in ta_h
    assert "TA_CMD_AES_GCM_DECRYPT" in ta_h
    assert "do_aes_gcm_encrypt" in ta_c
    assert "do_aes_gcm_decrypt" in ta_c

from app.tools.tee.ca_generator import CAGenerator


def test_ca_generator_aes_gcm_template_includes_commands():
    gen = CAGenerator()
    result = gen._build_files(name="aes_demo", ta_name="aes_demo", template="aes_gcm_simple")
    ca_c = result["aes_demo.c"]
    assert "TA_CMD_AES_GCM_ENCRYPT" in ca_c
    assert "TA_CMD_AES_GCM_DECRYPT" in ca_c
