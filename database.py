import os
from datetime import datetime
import random
import string
from sqlalchemy import create_engine, Column, Integer, String, DateTime, BigInteger, Text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255))
    first_name = Column(String(255))
    referral_code = Column(String(50), unique=True)
    referred_by = Column(BigInteger, nullable=True)
    referrals_count = Column(Integer, default=0)
    certificate_claimed = Column(Integer, default=0)
    certificate_id = Column(String(100), unique=True, nullable=True)
    claimed_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

class Referral(Base):
    __tablename__ = 'referrals'
    
    id = Column(Integer, primary_key=True)
    referrer_id = Column(BigInteger)
    referred_id = Column(BigInteger, unique=True)
    created_at = Column(DateTime, default=datetime.now)

class Database:
    def __init__(self):
        # Neon DB connection string
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is not set!")
        
        # Render uchun moslash: postgres:// -> postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        self.engine = create_engine(
            database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True
        )
        
        # Jadvallarni xavfsiz yaratish (agar mavjud bo'lmasa)
        self.create_tables_safely()
        
        self.Session = sessionmaker(bind=self.engine)
    
    def create_tables_safely(self):
        """Jadvallarni xavfsiz yaratish - mavjud bo'lsa, o'chirib tashlamaydi"""
        inspector = inspect(self.engine)
        
        # users jadvali mavjudligini tekshirish
        if not inspector.has_table('users'):
            User.__table__.create(self.engine)
            print("✅ users jadvali yaratildi")
        else:
            print("✅ users jadvali allaqachon mavjud")
        
        # referrals jadvali mavjudligini tekshirish
        if not inspector.has_table('referrals'):
            Referral.__table__.create(self.engine)
            print("✅ referrals jadvali yaratildi")
        else:
            print("✅ referrals jadvali allaqachon mavjud")
    
    def generate_referral_code(self, user_id):
        code = f"REF{user_id}{''.join(random.choices(string.ascii_uppercase + string.digits, k=5))}"
        return code
    
    def generate_certificate_id(self):
        cert_id = f"CERT-{datetime.now().strftime('%Y%m')}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"
        return cert_id
    
    def add_user(self, user_id, username, first_name, referred_by=None):
        session = self.Session()
        try:
            # Check if user exists
            existing = session.query(User).filter_by(user_id=user_id).first()
            if existing:
                return existing
            
            referral_code = self.generate_referral_code(user_id)
            
            new_user = User(
                user_id=user_id,
                username=username,
                first_name=first_name,
                referral_code=referral_code,
                referred_by=referred_by
            )
            session.add(new_user)
            
            # Agar referal orqali kelgan bo'lsa
            if referred_by and referred_by != user_id:
                # Check if already referred
                existing_ref = session.query(Referral).filter_by(referred_id=user_id).first()
                if not existing_ref:
                    referral = Referral(
                        referrer_id=referred_by,
                        referred_id=user_id
                    )
                    session.add(referral)
                    
                    # Update referrer's count
                    referrer = session.query(User).filter_by(user_id=referred_by).first()
                    if referrer:
                        referrer.referrals_count += 1
            
            session.commit()
            session.refresh(new_user)
            return new_user
            
        except Exception as e:
            session.rollback()
            print(f"Error adding user: {e}")
            return None
        finally:
            session.close()
    
    def get_user(self, user_id):
        session = self.Session()
        try:
            return session.query(User).filter_by(user_id=user_id).first()
        finally:
            session.close()
    
    def get_user_by_referral_code(self, code):
        session = self.Session()
        try:
            return session.query(User).filter_by(referral_code=code).first()
        finally:
            session.close()
    
    def get_referrals(self, user_id):
        session = self.Session()
        try:
            referrals = session.query(Referral).filter_by(referrer_id=user_id).all()
            result = []
            for ref in referrals:
                user = session.query(User).filter_by(user_id=ref.referred_id).first()
                if user:
                    result.append((
                        user.user_id,
                        user.username,
                        user.first_name,
                        ref.created_at
                    ))
            return result
        finally:
            session.close()
    
    def can_claim_certificate(self, user_id):
        user = self.get_user(user_id)
        if not user:
            return False, "Foydalanuvchi topilmadi"
        
        if user.certificate_claimed == 1:
            return False, "Siz allaqachon sertifikat olgansiz"
        
        if user.referrals_count >= 10:
            return True, "Sertifikat olishingiz mumkin!"
        else:
            return False, f"Sizga yana {10 - user.referrals_count} ta do'st kerak"
    
    def claim_certificate(self, user_id):
        session = self.Session()
        try:
            can_claim, message = self.can_claim_certificate(user_id)
            if not can_claim:
                return False, message
            
            cert_id = self.generate_certificate_id()
            
            user = session.query(User).filter_by(user_id=user_id).first()
            user.certificate_claimed = 1
            user.certificate_id = cert_id
            user.claimed_date = datetime.now()
            
            session.commit()
            return True, cert_id
            
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()
    
    def get_stats(self):
        session = self.Session()
        try:
            total_users = session.query(User).count()
            total_certificates = session.query(User).filter_by(certificate_claimed=1).count()
            total_referrals = session.query(Referral).count()
            
            return {
                'total_users': total_users,
                'total_certificates': total_certificates,
                'total_referrals': total_referrals
            }
        finally:
            session.close()
