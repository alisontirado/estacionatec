import os
from app import app, db
from models import Usuarios, Vehiculos, Pagos, CodigosQr, RegistroAcceso

def actualizar_base_datos():
    with app.app_context():
        try:
            print("🔄 Actualizando base de datos...")
            
            # Agregar columnas faltantes si no existen
            print("📝 Verificando columnas faltantes...")
            
            # Ejecutar SQL para agregar columnas si no existen
            from sqlalchemy import text
            
            # Verificar y agregar columnas a la tabla pagos
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    -- Agregar estado si no existe
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                  WHERE table_name='pagos' AND column_name='estado') THEN
                        ALTER TABLE pagos ADD COLUMN estado VARCHAR(20);
                    END IF;
                    
                    -- Agregar metodo_pago si no existe
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                  WHERE table_name='pagos' AND column_name='metodo_pago') THEN
                        ALTER TABLE pagos ADD COLUMN metodo_pago VARCHAR(50);
                    END IF;
                    
                    -- Agregar transaccion_id si no existe
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                  WHERE table_name='pagos' AND column_name='transaccion_id') THEN
                        ALTER TABLE pagos ADD COLUMN transaccion_id VARCHAR(100);
                    END IF;
                    
                    -- Actualizar valores por defecto para registros existentes
                    UPDATE pagos SET estado = 'completado' WHERE estado IS NULL;
                    UPDATE pagos SET metodo_pago = 'efectivo' WHERE metodo_pago IS NULL;
                END $$;
            """))
            
            db.session.commit()
            print("✅ Base de datos actualizada correctamente")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error al actualizar la base de datos: {e}")

if __name__ == '__main__':
    actualizar_base_datos()