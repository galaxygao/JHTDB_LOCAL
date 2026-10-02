import json
from dataclasses import replace
from pathlib import Path

import yaml
from streamlit.testing.v1 import AppTest

from jhtdb_pipeline.processing import process_batch
from test_processing import fixture


def test_full_field_gui_all_pages_and_boundary_slices(tmp_path, monkeypatch):
    cfg, _ = fixture(tmp_path)
    cfg = replace(cfg, fft_cache_mode='memmap', sigma_grids=(1.0, 2.0))
    paths = process_batch(cfg, 1)
    sbar_passed = json.loads((paths[0] / "s_bar_qa.json").read_text())["passed"]
    config = yaml.safe_load(Path('configs/pipeline.macos.yaml').read_text())
    config['platform'] = {key: str(getattr(cfg, key)) for key in ('state_root', 'run_root', 'result_root')}
    # GUI metadata discovery must read full test arrays, without allocating a production field.
    config_path = tmp_path / 'gui.yaml'
    config_path.write_text(yaml.safe_dump(config))
    monkeypatch.setenv('JHTDB_PIPELINE_CONFIG', str(config_path))
    app = AppTest.from_file(str(Path('src/jhtdb_pipeline/dashboard.py').resolve()), default_timeout=20)
    app.run()
    assert not app.exception
    app.sidebar.button[0].click().run()
    assert not app.exception
    for page in app.sidebar.radio[0].options:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, str(app.exception)
        if page == "全域 S̄ QA" and not sbar_passed:
            assert [item.value for item in app.error] == ["全域 S̄ QA：失败；正式数据仍保留用于诊断"]
        else:
            assert not app.error, (page, [item.value for item in app.error])
        if app.sidebar.slider:
            assert app.sidebar.slider[0].max == 15
            app.sidebar.slider[0].set_value(0).run()
            assert not app.exception, str(app.exception)
            app.sidebar.slider[0].set_value(15).run()
            assert not app.exception, str(app.exception)
