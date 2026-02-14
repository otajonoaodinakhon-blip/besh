from PIL import Image, ImageDraw, ImageFont
import qrcode
import os
from datetime import datetime

class CertificateGenerator:
    def __init__(self, template_path='template.png'):
        self.template_path = template_path
        # Render diskiga saqlash
        self.output_dir = os.path.join(os.getcwd(), 'certificates')
        os.makedirs(self.output_dir, exist_ok=True)
    
    def generate(self, user_data, certificate_id):
        """Sertifikat yaratish"""
        try:
            # Shablonni tekshirish
            if os.path.exists(self.template_path):
                img = Image.open(self.template_path)
            else:
                # Agar shablon bo'lmasa, oddiy fon yaratish
                img = Image.new('RGB', (1200, 800), color='white')
            
            draw = ImageDraw.Draw(img)
            
            # Fontlarni yuklash
            try:
                title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
                name_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
                text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
            except:
                title_font = ImageFont.load_default()
                name_font = ImageFont.load_default()
                text_font = ImageFont.load_default()
            
            # Sertifikat matnini yozish
            draw.text((600, 150), "CERTIFICATE", fill="#001b3b", font=title_font, anchor="mm")
            
            name = user_data[2] or f"User {user_data[0]}"
            draw.text((600, 350), "This certificate is proudly presented to", fill="#4a5568", font=text_font, anchor="mm")
            draw.text((600, 430), name, fill="#001b3b", font=name_font, anchor="mm")
            
            # QR Code yaratish
            qr = qrcode.QRCode(version=1, box_size=5, border=2)
            qr.add_data(f"https://omp.aistudy.uz/certificate?id={certificate_id}")
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            img.paste(qr_img, (50, 50))
            
            # Rasmni saqlash
            output_path = os.path.join(self.output_dir, f"{certificate_id}.png")
            img.save(output_path)
            
            return output_path
            
        except Exception as e:
            print(f"Sertifikat yaratishda xatolik: {e}")
            # Xatolik bo'lsa, oddiy fayl yaratish
            fallback_path = os.path.join(self.output_dir, f"{certificate_id}.txt")
            with open(fallback_path, 'w') as f:
                f.write(f"Certificate ID: {certificate_id}\nName: {user_data[2]}")
            return fallback_path