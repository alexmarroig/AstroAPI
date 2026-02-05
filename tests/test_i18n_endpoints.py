from fastapi.testclient import TestClient

import main


def test_i18n_catalog_has_ptbr_signs():
    client = TestClient(main.app)
    resp = client.get('/v1/i18n/ptbr')
    assert resp.status_code == 200
    body = resp.json()
    assert body['ok'] is True
    assert body['data']['signs']['scorpio'] == 'Escorpião'
    assert body['data']['signs']['sagittarius'] == 'Sagitário'


def test_i18n_validate_detects_english_signs():
    client = TestClient(main.app)
    payload = {
        'payload': {
            'headline': 'Lua minguante em Scorpio',
            'moon_sign': 'Scorpio',
            'nested': {'next_sign': 'Sagitário'},
        }
    }
    resp = client.post('/v1/i18n/validate', json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body['ok'] is True
    assert body['data']['valid'] is False
    assert '$.moon_sign' in body['data']['non_translated_fields']
