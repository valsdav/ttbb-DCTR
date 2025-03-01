import torch
import torch.nn as nn
import torch.nn.functional as F
import pytorch_lightning as pl
from torch.optim.lr_scheduler import CosineAnnealingLR, ExponentialLR

class BinaryClassifier(pl.LightningModule):
    def __init__(self, input_size, hidden_size, output_size, num_hidden_layers, learning_rate=1e-3, weight_decay=0, scheduler=None, T_max=None, gamma=None):
        super(BinaryClassifier, self).__init__()
        self.save_hyperparameters()
        self.criterion = nn.BCEWithLogitsLoss(reduction='none') # Note: with the BCEWithLogitsLoss, a sigmoid is applied to the output of the model

        layers = [
            nn.BatchNorm1d(input_size, affine=False), # Batch normalization layer
            nn.Linear(input_size, hidden_size) # Input layer
        ]
        
        # Stack N-1 hidden layers
        for _ in range(num_hidden_layers):
            layers.append(nn.ReLU())
            layers.append(nn.Linear(hidden_size, hidden_size)) # Hidden layers

        layers.append(nn.ReLU())
        layers.append(nn.Linear(hidden_size, output_size)) # Output layer

        self.layers = nn.Sequential(*layers)

    def forward(self, x):
        x = self.layers(x)
        
        return x

    def training_step(self, batch, batch_idx):
        x, y, w = batch
        y_pred = self(x)
        losses = self.criterion(y_pred.squeeze(), y.float())
        loss = (losses * w).mean()
        self.log('train_loss', loss)
        return loss

    def validation_step(self, batch, batch_idx):
        x, y, w = batch
        y_pred = self(x)
        losses = self.criterion(y_pred.squeeze(), y.float())
        loss = (losses * w).mean()
        self.log('val_loss', loss)
        return loss

    def test_step(self, batch, batch_idx):
        x, y, w = batch
        y_pred = self(x)
        losses = self.criterion(y_pred.squeeze(), y.float())
        loss = (losses * w).mean()
        self.log('test_loss', loss, prog_bar=True)
        return loss

    def predict_step(self, batch, batch_idx, dataloader_idx=None):
        x, y, w = batch
        y_pred = self(x)
        y_pred = torch.sigmoid(y_pred)
        return y_pred

    def configure_optimizers(self):
        optimizer = torch.optim.SGD(self.parameters(), lr=self.hparams.learning_rate, weight_decay=self.hparams.weight_decay)

        if self.hparams.scheduler is not None:
            if self.hparams.scheduler == "CosineAnnealingLR":
                assert self.hparams.T_max is not None, "T_max must be provided for CosineAnnealingLR scheduler. Please set it in the model hyperparameters."
                scheduler = CosineAnnealingLR(
                    optimizer,
                    T_max=self.hparams.T_max
                )
            elif self.hparams.scheduler == "ExponentialLR":
                assert self.hparams.gamma is not None, "gamma must be provided for ExponentialLR scheduler. Please set it in the model hyperparameters."
                scheduler = ExponentialLR(
                    optimizer,
                    gamma=self.hparams.gamma
                )
            else:
                raise NotImplementedError(f"Scheduler {self.hparams.scheduler} not implemented")

            return [optimizer], [scheduler]
        else:
            return optimizer


# Wrapper class with sigmoid function applied already in the forward pass
class WrappedModel(pl.LightningModule):
    def __init__(self, model):
        super(WrappedModel, self).__init__()
        self.model = model
        self.example_input_array = torch.rand(16, model.hparams.input_size)

    def forward(self, x):
        return F.sigmoid(self.model(x))
