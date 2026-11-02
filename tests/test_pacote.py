from importlib.metadata import version


def test_pacote_forms_esta_instalado_e_importavel():
    # act
    import forms

    # assert
    assert forms.__name__ == "forms"
    assert version("forms")
