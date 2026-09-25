import duckdb

DB_FILE = "web_decay_dw.db"

def get_db_connection():
    return duckdb.connect(DB_FILE)

def initialise_schema():
    print("Initialising database schema layers (Serverless Engine)...")

    ddl_queries = """
    CREATE TABLE IF NOT EXISTS dim_user (
        user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        username VARCHAR(100) UNIQUE NOT NULL,
        email VARCHAR(255) NOT NULL,
        notification_pref VARCHAR(20) DEFAULT 'slack',
        slack_webhook_url TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
        is_active BOOLEAN DEFAULT TRUE,
        timezone VARCHAR(50) DEFAULT 'UTC'
    );

    CREATE TABLE IF NOT EXISTS dim_domain (
        domain_hash VARCHAR(64) PRIMARY KEY,
        domain_name VARCHAR(255) UNIQUE NOT NULL,
        top_level_domain VARCHAR(20) NOT NULL,
        registered_year INT,
        is_malicious BOOLEAN DEFAULT FALSE
    ); 

    CREATE TABLE IF NOT EXISTS dim_hackernews_item (
        item_id INTEGER PRIMARY KEY,
        author_user VARCHAR(100) NOT NULL,
        item_name TEXT NOT NULL,
        item_type VARCHAR(50) NOT NULL,
        score INTEGER DEFAULT 0,
        descendants INTEGER DEFAULT 0,
        posted_at_timestamp TIMESTAMP WITH TIME ZONE NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sys_pipeline_log (
        log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        dag_run_id VARCHAR(100),
        job_name VARCHAR(100) NOT NULL,
        started_at TIMESTAMP WITH TIME ZONE NOT NULL,
        ended_at TIMESTAMP WITH TIME ZONE,
        status VARCHAR(20) NOT NULL,
        records_processed INTEGER DEFAULT 0,
        error_message TEXT
    );

    CREATE TABLE IF NOT EXISTS dim_domain_history (
        history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        domain_hash VARCHAR(64) REFERENCES dim_domain(domain_hash),
        reliability_tier VARCHAR(50) NOT NULL,
        valid_from TIMESTAMP WITH TIME ZONE NOT NULL,
        valid_to TIMESTAMP WITH TIME ZONE,
        is_current BOOLEAN DEFAULT TRUE,
        previous_reliability_tier VARCHAR(50),
        change_reason TEXT
    );

    CREATE TABLE IF NOT EXISTS fact_link_status (
        check_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        item_id INTEGER REFERENCES dim_hackernews_item(item_id),
        domain_hash VARCHAR(64) REFERENCES dim_domain(domain_hash),
        log_id UUID REFERENCES sys_pipeline_log(log_id),
        raw_url TEXT NOT NULL,
        http_status_code INTEGER,
        response_time_ms INTEGER,
        is_dead BOOLEAN NOT NULL,
        error_type VARCHAR(100),
        check_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS fact_alerts (
        alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID REFERENCES dim_user(user_id),
        check_id UUID REFERENCES fact_link_status(check_id),
        log_id UUID REFERENCES sys_pipeline_log(log_id),   
        alert_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        delivery_status VARCHAR(50) NOT NULL,
        retry_count INTEGER DEFAULT 0,
        channel_used VARCHAR(50) NOT NULL,
        payload_size_bytes INTEGER,
        resolved_at TIMESTAMP WITH TIME ZONE
    );
    """

    conn = get_db_connection()
    try:
        conn.execute(ddl_queries)
        print("Schema integrated and verified natively.")
    except Exception as e:
        print(f"Failed to initialise schema: {e}")
    finally:
        conn.close()

def start_pipeline_log(job_name: str) -> str:
    conn = get_db_connection()
    try:
        res = conn.execute("""
            INSERT INTO sys_pipeline_log (job_name, started_at, status)
            VALUES (?, CURRENT_TIMESTAMP, 'RUNNING')
            RETURNING log_id;
        """, (job_name,)).fetchone()
        return res[0] if res else None
    except Exception as e:
        print(f"Failed to log pipeline start: {e}")
        return None
    finally:
        conn.close()

def end_pipeline_log(log_id: str, status: str, records_processed: int, error_message: str = None):
    conn = get_db_connection()
    try:
        conn.execute("""
            UPDATE sys_pipeline_log
            SET ended_at = CURRENT_TIMESTAMP,
                status = ?,
                records_processed = ?,
                error_message = ?
            WHERE log_id = ?;
        """, (status, records_processed, error_message, log_id))
    except Exception as e:
        print(f"Failed to log pipeline end: {e}")
    finally:
        conn.close()

def save_pipeline_data(item_data, domain_info, status_info, log_id):
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO dim_hackernews_item (item_id, author_user, item_name, item_type, score, descendants, posted_at_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (item_id) DO UPDATE SET
                score = EXCLUDED.score,
                descendants = EXCLUDED.descendants;
        """, (
            item_data['item_id'], item_data['author'], item_data['title'],
            item_data['item_type'], item_data['score'], item_data['descendants'], item_data['posted_at']   
        ))

        conn.execute("""
            INSERT INTO dim_domain (domain_hash, domain_name, top_level_domain)
            VALUES (?, ?, ?)
            ON CONFLICT (domain_hash) DO NOTHING;
        """, (
            domain_info['domain_hash'], domain_info['domain_name'], domain_info['tld']
        ))

        conn.execute("""
            INSERT INTO fact_link_status (item_id, domain_hash, log_id, raw_url, http_status_code, response_time_ms, is_dead, error_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            item_data['item_id'], domain_info['domain_hash'], log_id,
            item_data['raw_url'], status_info['http_status_code'],
            status_info['response_time_ms'], status_info['is_dead'], status_info['error_type']
        ))
    except Exception as e:
        print(f"Database insert error: {e}")
    finally:
        conn.close()

