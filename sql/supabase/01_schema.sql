-- 전국 저수지 목록: Supabase 테이블 만들기 (scripts/export_sql.py 로 생성)
-- 1) 이 파일 -> 2) 02_data_1.sql ~ 02_data_5.sql 순서로 SQL Editor 에서 실행하세요.
-- 주의: reservoirs 테이블이 이미 있으면 지우고 새로 만듭니다.
-- 예전 버전이 만들던 뷰가 남아 있으면 지운다 (지금은 테이블 하나만 사용)
DROP VIEW IF EXISTS reservoir_region_counts;
DROP TABLE IF EXISTS reservoirs;
CREATE TABLE reservoirs (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source VARCHAR(20),
  facility_code VARCHAR(30),
  name VARCHAR(100) NOT NULL,
  sido VARCHAR(20),
  sigungu VARCHAR(40),
  address VARCHAR(255),
  road_address VARCHAR(255),
  manager VARCHAR(100),
  total_storage DECIMAL(14,4),
  effective_storage DECIMAL(14,4),
  benefit_area DECIMAL(14,4),
  basin_area DECIMAL(14,4),
  full_water_area DECIMAL(14,4),
  dam_height DECIMAL(10,2),
  dam_length DECIMAL(10,2),
  completed_year SMALLINT,
  latitude DECIMAL(10,7),
  longitude DECIMAL(10,7),
  base_date DATE
);
COMMENT ON TABLE reservoirs IS '전국 저수지 목록';
COMMENT ON COLUMN reservoirs.source IS '출처';
COMMENT ON COLUMN reservoirs.facility_code IS '시설코드(관리번호)';
COMMENT ON COLUMN reservoirs.name IS '시설명';
COMMENT ON COLUMN reservoirs.sido IS '시도';
COMMENT ON COLUMN reservoirs.sigungu IS '시군구';
COMMENT ON COLUMN reservoirs.address IS '지번주소';
COMMENT ON COLUMN reservoirs.road_address IS '도로명주소';
COMMENT ON COLUMN reservoirs.manager IS '관리기관';
COMMENT ON COLUMN reservoirs.total_storage IS '총저수량(천㎥)';
COMMENT ON COLUMN reservoirs.effective_storage IS '유효저수량(천㎥)';
COMMENT ON COLUMN reservoirs.benefit_area IS '수혜면적(ha)';
COMMENT ON COLUMN reservoirs.basin_area IS '유역면적(ha)';
COMMENT ON COLUMN reservoirs.full_water_area IS '만수면적(ha)';
COMMENT ON COLUMN reservoirs.dam_height IS '제당높이(m)';
COMMENT ON COLUMN reservoirs.dam_length IS '제당길이(m)';
COMMENT ON COLUMN reservoirs.completed_year IS '준공연도';
COMMENT ON COLUMN reservoirs.latitude IS '위도';
COMMENT ON COLUMN reservoirs.longitude IS '경도';
COMMENT ON COLUMN reservoirs.base_date IS '데이터기준일자';
CREATE INDEX idx_reservoirs_region ON reservoirs (sido, sigungu);
CREATE INDEX idx_reservoirs_name ON reservoirs (name);

-- 이름·주소 부분검색(ILIKE '%동막%')을 빠르게
CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA extensions;
CREATE INDEX idx_reservoirs_name_trgm ON reservoirs USING gin (name extensions.gin_trgm_ops);

-- 누구나 읽기만 가능 (쓰기 정책이 없으므로 anon/authenticated 키로는 수정 불가)
ALTER TABLE reservoirs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "reservoirs are readable by everyone" ON reservoirs
  FOR SELECT TO anon, authenticated USING (true);
GRANT SELECT ON reservoirs TO anon, authenticated;
