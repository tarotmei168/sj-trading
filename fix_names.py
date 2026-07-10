content = open('daily_report_v2.py','r',encoding='utf-8').read()
name_map = {
    '5351':'鈺創','2369':'菱生','8016':'矽創','2464':'盟立','3588':'通嘉',
    '00947':'台新IC設計','3545':'敦泰','3003':'健和興','6693':'廣閎科',
    '6147':'頎邦','2316':'楠梓電','8358':'金居','4961':'天鈺','6187':'萬潤',
    '2458':'義隆','3234':'光環','6155':'鈞寶','8121':'越峰','6257':'矽格',
    '3026':'禾伸堂','6435':'大中','2493':'揚博','5493':'三聯','8086':'宏捷科',
    '2492':'華新科','8028':'昇陽半導體','3455':'由田','2481':'強茂',
    '6944':'兆聯實業','3532':'台勝科','2308':'台達電',
}
for sid, ch_name in name_map.items():
    old = f'"name":"{sid}"'
    new = f'"name":"{ch_name}"'
    if old in content:
        content = content.replace(old, new)
        print(f'Fixed {sid} -> {ch_name}')
open('daily_report_v2.py','w',encoding='utf-8').write(content)
print('All done')
