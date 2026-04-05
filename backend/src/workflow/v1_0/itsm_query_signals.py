"""ITSM 인텐트 분류용 키워드 시그널 목록."""

# ITSM Agent 관련 키워드 (한국어 + 영어)
ITSM_KEYWORDS: list[str] = [
    # 계정/권한
    "access", "권한", "계정", "아이디", "id", "비밀번호", "패스워드", "password",
    "로그인", "login", "접속", "인증", "authentication", "authorization",
    "권한 요청", "계정 생성", "계정 잠김", "계정 비활성",
    # 에러/오류
    "에러", "오류", "error", "fault", "exception", "fail", "실패",
    "장애", "이슈", "issue", "bug", "버그", "문제", "problem",
    "timeout", "타임아웃", "hang", "응답 없음", "deadlock", "데드락",
    # 시스템/서비스
    "서비스", "service", "시스템", "system", "서버", "server",
    "인터페이스", "interface", "if", "배치", "batch", "스케줄",
    "프로세스", "process", "프로그램", "program", "application",
    # 인프라/네트워크
    "네트워크", "network", "연결", "connection", "방화벽", "firewall",
    "vpn", "ssh", "ftp", "sftp", "포트", "port", "ip",
    "dns", "proxy", "프록시", "라우팅", "routing",
    # 데이터베이스
    "db", "database", "데이터베이스", "oracle", "sql", "쿼리", "query",
    "테이블", "table", "락", "lock", "트랜잭션", "transaction",
    "deadlock", "데이터 오류", "데이터 불일치",
    # MES/ERP 시스템
    "mes", "erp", "sap", "wip", "lot", "공정", "설비",
    "equipment", "recipe", "레시피", "파라미터", "parameter",
    "실적", "생산", "라인", "line", "fab",
    # 운영
    "설치", "install", "배포", "deploy", "업그레이드", "upgrade",
    "패치", "patch", "백업", "backup", "복구", "restore", "recovery",
    "재기동", "restart", "재시작", "shutdown", "기동",
    # 요청
    "요청", "request", "신청", "처리", "조치", "해결", "resolve",
    "문의", "inquiry", "support", "지원", "헬프", "help",
]

# 높은 가중치 키워드 (이것만 있어도 ITSM으로 분류)
HIGH_CONFIDENCE_KEYWORDS: list[str] = [
    "mes", "erp", "sap", "wip", "lot", "fab",
    "장애", "에러", "오류", "권한 요청", "계정 잠김",
    "배치 실패", "인터페이스 오류", "if 오류",
]
