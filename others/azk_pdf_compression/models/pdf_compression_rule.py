import base64
from datetime import datetime, timedelta
import glob
import io
import logging
import os
import time
import re
from tempfile import TemporaryFile
from PIL import Image
import PIL
import pikepdf
import zlib

from odoo import models, fields, api, exceptions

log = logging.getLogger(__name__)

class CompressionRules(models.Model):
    _name = 'pdf.compress.rules'
    
    name = fields.Char(string="Name", help ="Name of the rule")
    active = fields.Boolean(string="Active", default=True, help="Set to active for the scheduled action to run it")
    models = fields.Many2many('ir.model', string="Model(s)", help="Compress only attachments to the selected models")
#     destination_format = fields.Selection(
#             [('jpeg','jpeg'),
#             ('png','png'),
#             ('bmp','bmp'),
#             ('gif','gif'),
#             ('ico','ico'),
#             ('j2p','j2p'),
#             ('jpx','jpx'),
#             ('tif','tif'),
#             ('webp','webp'),],
#             'Destination Format', default='jpeg', required=True)
    min_size = fields.Integer(string="Minimum size (KB)",help="Minimum size to match (KB)", default=200)
    quality = fields.Integer(string="Quality", help="0 to 100 the lower the value the maximum compression", default=90)
    reduction_ratio = fields.Float(string='Reduction Ratio', default=0.5 ,help="")
    min_image_width_to_reduce_px = fields.Integer(string="Min Image Width To Reduce (PX)", default=300, help="Minimum image width in pixel to match, Images below this size will not be reduced")
    replace_all = fields.Boolean(string="Replace all", default=True, help="Compress all instances that have the same image content even if it matches another model")
    newer_than = fields.Integer(string="Newer than (days)", help="Process attachments that where added from newer_than days till now")
    older_than = fields.Integer(string="Older than (days)",help="Process attachments that where added before older_than days till now")
   
    
    @api.constrains('quality')
    def _validate_quality(self):
      for rec in self:
        if rec.quality and (rec.quality > 100 or rec.quality < 0):
             raise exceptions.ValidationError("""Quality should be between ]0 and 100] for: %s""" % (rec.name))
           
        
    @api.constrains('reduction_ratio')
    def _validate_reduction_ratio(self):
        for rec in self:
            if rec.reduction_ratio and (rec.reduction_ratio > 1 or rec.reduction_ratio < 0):
                raise exceptions.ValidationError("""Reduction ratio should be between [0 and 1]  for %s""" %s (rec.name) )
    
    def execute_rule(self, res_model=None, res_id=None, limit=50):
        """
        @param res_model: (string) if specified with res_id it selects that model attachment and compresses them
        @param res_id: works with res_model to filter only attachments for that res_model,res_id  
        @param limit: default to 50 in order to prevent timeout if ran from UI
        """
        compressed_attachments = 0
        compressed_fnames = set()
        total_start_size = 0
        total_final_size = 0
        
        for rule in self:
            model_names = list(map(lambda m:m.model, rule.models))
            if res_model and res_id:
                attach_search_domain = [
                                        '|', ('res_field', '!=', False), ('res_field', '=', False),
                                        ('res_model', '=', res_model),
                                        ('res_id', '=', res_id)
                                        ]
            else:  
                attach_search_domain = [('id', '!=', False),
                                        ('pdf_compressed_on', '=', False),
                                        ('res_model', 'in', model_names),
                                        ('file_size', '>=', (rule.min_size * 1000)),]
            
                if rule.newer_than and rule.newer_than > 0:
                    attach_search_domain.append(('create_date', '>', datetime.now()-timedelta(days=rule.newer_than)))
             
                if rule.older_than and rule.older_than > 0:
                    attach_search_domain.append(('create_date', '<', datetime.now()-timedelta(days=rule.older_than)))
            
            attachments = self.env['ir.attachment'].search(attach_search_domain).filtered(lambda r: r.mimetype=='application/pdf')
            if limit:
                attachments = attachments[0:limit]
            
            log.info("Matched %s records using rule: %s from source format PDF  with minimum size %s , newer than %s days and older than %s days and model/res_id: %s[%s] with search domain: %s with limit: %s", 
                        len(attachments), rule.name,rule.min_size,rule.newer_than,rule.older_than, res_model, res_id, attach_search_domain, limit)
            
            for atc in attachments:
                orig_fname = atc.store_fname
                
                if orig_fname not in compressed_fnames:
                    before = time.time()
                    old_pdf_deleted = False
                    
                    try:
                        orig_size = atc.file_size
                        
                        is_attachment = True
                        temp_file = None
                        
                        if atc.db_datas:
                            is_attachment = False
                            temp_file = TemporaryFile('wb+')
                            temp_file.write(atc.db_datas)
                            pdf = self.compress_pdf(atc.db_datas, rule.reduction_ratio, rule.min_image_width_to_reduce_px, rule.quality)
                        else:
                            file_path = atc._full_path(atc.store_fname)
                            pdf =  self.compress_pdf(file_path, rule.reduction_ratio, rule.min_image_width_to_reduce_px, rule.quality)
                    
                        compressed_pdf = io.BytesIO()
                        pdf.save(compressed_pdf, recompress_flate=True, compress_streams=True)
                        pdf.close()
                        
                        compressed_bytes = compressed_pdf.getvalue()
                        checksum = atc._compute_checksum(compressed_bytes)
                         
            
                        old_name = atc.name
                        filename, file_extension = os.path.splitext(old_name)
                        new_name = '%s.%s' % (filename, 'pdf')
                        
                    
                        update_dict = {
                            'name' : new_name,
                            'display_name' : new_name,
                            'mimetype': 'application/pdf',
                             'file_size': len(compressed_bytes),
                            'pdf_compressed_on': datetime.now()
                            }
                        
                        atc.write(update_dict)
                        new_file_data = atc._get_datas_related_values(compressed_bytes, 'application/pdf')
                        update_dict.update(new_file_data)

                        encoded_bytes = base64.b64encode(compressed_bytes)
                        update_dict.update({'datas': encoded_bytes})
                        
                        atc.write(update_dict)
                        new_size = len(compressed_pdf.getvalue())
                        
                        if rule.replace_all and is_attachment:
                            compressed_fnames.add(orig_fname)
                            attachments_copy = self.env['ir.attachment'].search([('id', '!=', atc.id),('store_fname', '=', orig_fname)])
                            
                            for d_act in attachments_copy:
                                    d_act.write({
                                                'name' : '%s.%s' % (os.path.splitext(d_act.name)[0], 'pdf'),
                                                'mimetype': 'application/pdf',
                                                'datas': encoded_bytes,
                                                'pdf_compressed_on': datetime.now()
                                                })
                                    d_act.write(update_dict) 
                                    
                                    if d_act.res_field:
                                        self.fix_model_filename(d_act)
                                        
                            compressed_fnames.add(update_dict['name'])
                            
                        compressed_attachments += 1
                        total_start_size += orig_size
                        total_final_size += new_size
                        
                        if atc.res_field:
                            self.fix_model_filename(atc)
                            
                        if self.env['ir.attachment'].search_count([('store_fname', '=', orig_fname)]) == 0:
                            self.env.cr.commit()
                            os.remove(file_path)
                            old_pdf_deleted = True

                        if temp_file:
                            temp_file.close()

                        log.info("Compressing attachment for: %s, %s[%s] %s from size:%s to: %s created: %s new fname: %s  deleted: %s in %0.2fs",
                                  atc.id, atc.res_model, atc.res_id, orig_fname, "{:,}".format(orig_size), "{:,}".format(new_size), atc.create_date, atc.store_fname, old_pdf_deleted, time.time() - before)

                    except:
                        log.error("Failed to process %s for pdf: %s and rule: %s", atc, atc.store_fname, rule, exc_info=1)
                        
        res = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Compression Done',
                    'message': 'Compressed %s pdf attachments from total size %s to %s.' % (compressed_attachments,"{:,}".format(total_start_size),"{:,}".format(total_final_size)),
                    'sticky': False,
                    'type': 'success',
                }
            }
            
        return res
    
    def compress_pdf(self, file_path, reduction_ratio=0.5, min_image_width_to_reduce_px=300, quality_ratio=70, dest_format='jpeg'):
        pdf = pikepdf.Pdf.open(file_path)
        for pg_idx, page in enumerate(pdf.pages):
            for img_key, raw_img in page.images.items():
                try:
                    pdf_img = pikepdf.PdfImage(raw_img)
                    pil_img = pdf_img.as_pil_image()
            
                    if pil_img.size[0] >= min_image_width_to_reduce_px and int(pil_img.size[0]*reduction_ratio) <= pil_img.size[0]:
                        if pil_img.mode in ['P', 'RGBA']:
                            pil_img = pil_img.convert('RGB')
                        pil_resized = pil_img.resize((int(pil_img.size[0]*reduction_ratio), int(pil_img.size[1]*reduction_ratio)))
                        
                        b = io.BytesIO()
                        pil_resized.save(b, format=dest_format, optimize=True, quality=quality_ratio)
                        b.seek(0)
                        img_bytes = b.read()
            
                        raw_img.write(img_bytes, filter=pikepdf.Name("/DCTDecode"))
                        #raw_img.ColorSpace = pikepdf.Name("/DeviceRGB")
                        raw_img.Width, raw_img.Height = pil_resized.size
            
                        print(f"Image size for '${img_key}' is: {pil_img.size} resized to: {pil_resized.size}")
            
                    else:
                        print(f"Skip Image resize for '${img_key}' with: {pil_img.size} min {min_image_width_to_reduce_px}")
                except:
                    print(f"Skip Image resize for '${img_key}' from pdf file '${file_path}' while failed to get raw bytes")
        
        return pdf
#         pdf.save(r'data\pdf.promotobillet-ratio-%s.pdf' % (REDUCTION_RATIO, ))  
        
    @api.model
    def _execute_rules(self, limit=None):
        ''' called by cron job '''
        active_rules = self.env['pdf.compress.rules'].search([('active', '!=', False)])
        
        active_rules.execute_rule(limit=limit)
            
    def fix_model_filename(self, attachment):
        model_rec = self.env[attachment.res_model].search([('id', '=', attachment.res_id)])
        model_fieldname = '%s_filename' % (attachment.res_field, )
        
        if hasattr(model_rec, model_fieldname):
            old_model_filename = getattr(model_rec, model_fieldname)
            filename, file_extension = os.path.splitext(old_model_filename)
            new_model_filename = '%s.%s' % (filename,'pdf')
            setattr(model_rec, model_fieldname, new_model_filename)
    
    
class DebugRule(models.TransientModel):
    _name = "pdf.debug.rule"
    
    res_model = fields.Char(string="Model", help="Select the specific model to run the rule on")
    res_id = fields.Char(string="Resource ID", help="Select the ID of the Object to run this rule on")

    def execute_debug_rule(self):
        rule = self.env['pdf.compress.rules'].browse(self.env.context.get('active_id'))
        rule.execute_rule(self.res_model, self.res_id)
        
    
class Attachments(models.Model):
    _inherit = 'ir.attachment'
    
    pdf_compressed_on = fields.Datetime(string="PDF Compressed On", readonly=True, default = None)
