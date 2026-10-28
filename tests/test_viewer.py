def test_viewer_module_imports_without_creating_a_gui_window():
    from smart_pdf_compare import viewer

    assert callable(viewer.launch_viewer)
