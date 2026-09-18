"""Explainable page-layout estimates, not a trained book-genre classifier."""
import re
import cv2
import numpy as np

PAGE_LABELS={'english_book':'영어 글 중심','text_book':'글이 많은 페이지','picture_book':'그림 중심','math_book':'수학·계산', 'art_book':'미술·창작', 'uncertain':'판단 보류'}


def analyze_page(image, data):
    height,width=image.shape[:2]
    scale=min(1,700/max(height,width))
    small=cv2.resize(image,(max(1,round(width*scale)),max(1,round(height*scale))))
    gray=cv2.cvtColor(small,cv2.COLOR_BGR2GRAY)
    hsv=cv2.cvtColor(small,cv2.COLOR_BGR2HSV)
    # Compare dark marks with their local paper background so shadows do not
    # count as a full-page illustration. Saturated regions retain flat artwork.
    background=cv2.morphologyEx(gray,cv2.MORPH_CLOSE,np.ones((41,41),np.uint8))
    dark_marks=gray.astype(np.float32)<background.astype(np.float32)*.75
    ink=(dark_marks|((hsv[:,:,1]>70)&(hsv[:,:,2]<250))).astype(np.uint8)*255
    mask=np.zeros(gray.shape,np.uint8)
    words=[]; lines=set(); confidences=[]
    for index,word in enumerate(data['text']):
        confidence=float(data['conf'][index])
        if not word.strip() or confidence<40: continue
        words.append(word); confidences.append(confidence)
        lines.add(tuple(data[key][index] for key in ('block_num','par_num','line_num')))
        x,y,w,h=(round(data[key][index]*scale) for key in ('left','top','width','height'))
        cv2.rectangle(mask,(max(0,x-2),max(0,y-2)),(min(mask.shape[1]-1,x+w+2),min(mask.shape[0]-1,y+h+2)),255,-1)
    ink[mask>0]=0
    graphics=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((9,9),np.uint8))
    graphic_ratio=float(np.mean(graphics>0))
    text_ratio=float(np.mean(mask>0))
    text=' '.join(words)
    latin=len(re.findall('[A-Za-z]',text)); hangul=len(re.findall('[가-힣]',text))
    characters=latin+hangul
    latin_ratio=latin/max(1,characters)
    sharpness=float(cv2.Laplacian(gray,cv2.CV_64F).var())
    kind='uncertain'; reason='페이지를 크게, 흔들림 없이 촬영해 주세요.'
    if sharpness>=15:
        math_words = re.search(r'수학|방정식|덧셈|뺄셈|곱셈|나눗셈|\b(?:math|mathematics|algebra|geometry)\b', text, re.I)
        math_indices = [i for i,w in enumerate(data['text']) if w.strip()]
        math_text = ' '.join(data['text'][i] for i in math_indices)
        math_lines = {tuple(data[k][i] for k in ('block_num','par_num','line_num')) for i in math_indices}
        math_terms = re.findall(r'자연수|유리수|무리수|다항식|부등식|함수|분수|소인수|거듭제곱|미분|적분|삼각형|확률|지수|로그', math_text)
        math_evidence = len(math_terms)>=2 and len(math_lines)>=2
        art_words = re.search(r'미술|색칠|그리기|드로잉|\b(?:drawing|painting|sketching)\b', text, re.I)
        equations = re.findall(r'[0-9a-z]\s*[+×÷=]\s*[0-9a-z]', text, re.I)
        if math_evidence or (len(lines)>=2 and (math_words or len(equations)>=3)):
            kind='math_book'; reason='수학 용어나 반복되는 계산식이 인식됐습니다.'
        elif len(lines)>=2 and art_words:
            kind='art_book'; reason='미술·그리기 활동을 나타내는 글이 인식됐습니다.'
        elif graphic_ratio>=.28 and text_ratio<.15:
            kind='picture_book'; reason='큰 그림 영역이 많고 인식된 글 영역은 적습니다.'
        elif characters>=40 and latin_ratio>=.7 and len(lines)>=2:
            kind='english_book'; reason='읽힌 글자의 대부분이 영어 알파벳입니다.'
        elif characters>=80 and len(lines)>=4:
            kind='text_book'; reason='여러 줄의 글이 충분히 인식된 글 중심 페이지입니다.'
    return {'kind':kind,'label':PAGE_LABELS[kind],'eligible':kind!='uncertain','reason':reason,
            'metrics':{'recognized_characters':characters,'text_lines':len(lines),
                       'latin_ratio':round(latin_ratio,3),'text_area_ratio':round(text_ratio,3),
                       'graphic_area_estimate':round(graphic_ratio,3),'sharpness':round(sharpness,1)},
            'method':'local_layout_rules'}
